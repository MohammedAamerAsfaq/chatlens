"""Real Estate Location: where an inquiry's property is.

After extraction (and for older inquiries through the Area Map backfill), an AI agent reads
the whole inquiry - group or chat name, sender, summary, original message and the extracted
properties - and names each property's area (community or district), sub-area (building,
cluster or project) and city. Its instructions are the company's "Real Estate Location"
prompt in AI Instructions; it may use live web search when the company turns that on.

Each area is then placed on the map once per company (AreaLocation): from the geography
directory when it has exactly one match, otherwise with Google Maps text search for
"area, city, country" inside the Google Maps monthly request cap.
"""

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.integrations.services.geography_sync import normalize_name
from apps.real_estate.models import (
    AreaLocation, OpportunityItem, RealEstateAgentCallLog, RealEstatePromptConfig, RealEstateSettings,
)
from apps.real_estate.services.agent_call import call_real_estate_agent
from apps.real_estate.services.prompts import configured_prompt, target_prompt_config
from apps.real_estate.services.response_parser import parse_json_object

TASK_KEY = 'real_estate.locate_opportunity'
LIVE_PRIORITY = 50
BACKFILL_PRIORITY = 200
WEB_SEARCH_RESULTS = 3
KNOWN_AREAS_LIMIT = 200

# Added to the company's Location instructions (stock or edited) on every call, so the same
# area is always written the same way and counts as one area on the map.
_NAMING_RULE = """Area names: use the community's full official name and write it the same way every time.
Give sub_area as the building, cluster or project's own name, without adding words such as
"cluster" or "tower" that are not part of that name."""
_KNOWN_AREAS_RULE = """Areas this company already has, with their city. When the property is in one of these,
use that area and city exactly as written here:"""

_SEARCH_RULES = {
    RealEstateSettings.LOCATION_SEARCH_MODEL: (
        'Use your own knowledge of this market\'s communities, projects, clusters and buildings.'
    ),
    RealEstateSettings.LOCATION_SEARCH_WEB: (
        'Web search results are provided with this request. Use them to check which community a '
        'building, cluster or project belongs to, especially for names you are not sure of.'
    ),
}


def enqueue_location(opportunity, *, priority=LIVE_PRIORITY):
    """Queue the Location step for an opportunity that has property items."""
    from apps.queue_management.services import enqueue_task

    if not opportunity.items.exists():
        return None
    return enqueue_task(
        task_key=TASK_KEY,
        payload={'version': 1, 'company_id': opportunity.company_id, 'opportunity_id': opportunity.pk},
        priority=priority,
        idempotency_key=f'real-estate-locate:{opportunity.pk}',
        correlation_id=f'real-estate-opportunity:{opportunity.pk}',
        company=opportunity.company,
    )


def location_call(company):
    """(system prompt, prompt config whose AI target to use, extra agent-call options) for the
    Location step. With no model chosen for the Location prompt, the extraction prompt's
    model is used."""
    system_prompt, _config = configured_prompt(company, RealEstatePromptConfig.KEY_LOCATION)
    settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
    mode = settings_row.location_search_mode
    if mode not in _SEARCH_RULES:
        raise ValueError(f'Unknown location search mode: {mode!r}.')
    options = {'web_search': {'max_results': WEB_SEARCH_RESULTS}} if mode == RealEstateSettings.LOCATION_SEARCH_WEB else {}
    parts = [system_prompt, _SEARCH_RULES[mode], _NAMING_RULE]
    known = known_areas(company)
    if known:
        parts.append(_KNOWN_AREAS_RULE + '\n' + '\n'.join(known))
    return '\n\n'.join(parts), target_prompt_config(company, RealEstatePromptConfig.KEY_LOCATION), options


def known_areas(company):
    """The company's areas with the most inquiries, as "- name, city" lines."""
    rows = (
        AreaLocation.objects.filter(company=company, merged_into__isnull=True)
        .annotate(uses=Count('opportunity_items'))
        .filter(uses__gt=0)
        .order_by('-uses', 'name')[:KNOWN_AREAS_LIMIT]
    )
    return [f'- {row.name}, {row.city}' if row.city else f'- {row.name}' for row in rows]


def inquiry_context(opportunity, items):
    chat = opportunity.source_chat
    contact = opportunity.contact
    lines = [
        f'Chat: {chat.name or "unnamed"} ({chat.chat_type})' if chat else 'Chat: none (entered by hand)',
        f'Sender: {_sender(opportunity, contact)}',
        f'Activity: {opportunity.activity_type or "unknown"}',
        f'Summary: {opportunity.summary or "none"}',
        'Original message:',
        opportunity.original_message or '(none)',
        '',
        'Properties:',
    ]
    for item in items:
        parts = [f'{item.sequence}.']
        if item.title:
            parts.append(f'title: {item.title}')
        if item.property_type_label:
            parts.append(f'type: {item.property_type_label}')
        parts.append(f'location words: {", ".join(item.locations) if item.locations else "none"}')
        if item.location_raw:
            parts.append(f'location text: {item.location_raw}')
        address = _linked_address(item)
        if address:
            parts.append(f'linked property address: {address}')
        lines.append(' | '.join(parts))
    return '\n'.join(lines)


def locate_opportunity(opportunity, *, include_manual=False):
    """Run the Location AI step for the opportunity's items and place their areas. Items
    located or cleared by hand are left alone unless include_manual (the inquiry card's
    explicit "Find with AI")."""
    items = opportunity.items.select_related('property__address').order_by('sequence')
    if not include_manual:
        items = items.exclude(geo_source=OpportunityItem.GEO_SOURCE_MANUAL)
    items = list(items)
    if not items:
        return []
    company = opportunity.company
    try:
        system_prompt, prompt_config, options = location_call(company)
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': inquiry_context(opportunity, items)},
        ]
        response = call_real_estate_agent(
            purpose=RealEstateAgentCallLog.PURPOSE_LOCATION,
            messages=messages,
            company=company,
            prompt_config=prompt_config,
            wa_message_id=opportunity.source_message_id,
            correlation_id=f'real-estate-opportunity:{opportunity.pk}',
            temperature=0,
            **options,
        )
        answers = parse_location_response(response)
    except Exception as exc:
        OpportunityItem.objects.filter(pk__in=[item.pk for item in items]).update(
            geo_status=OpportunityItem.GEO_ERROR, geo_error=str(exc)[:2000], updated_at=timezone.now(),
        )
        raise
    now = timezone.now()
    for item in items:
        answer = answers.get(item.sequence)
        if answer is None:
            item.geo_status, item.geo_error = OpportunityItem.GEO_ERROR, 'The AI returned no location for this property.'
            item.geo_area = item.geo_sub_area = item.geo_city = item.geo_basis = ''
            item.geo_confidence, item.geo_area_location = None, None
        else:
            item.geo_area, item.geo_sub_area, item.geo_city = answer['area'], answer['sub_area'], answer['city']
            item.geo_confidence, item.geo_basis, item.geo_error = answer['confidence'], answer['basis'], ''
            if answer['area']:
                item.geo_status = OpportunityItem.GEO_LOCATED
                item.geo_area_location = area_location_for(company, answer['area'], answer['city'])
                item.geo_area, item.geo_city = item.geo_area_location.name, item.geo_area_location.city
            else:
                item.geo_status, item.geo_area_location = OpportunityItem.GEO_UNKNOWN, None
        item.geo_located_at, item.geo_source = now, OpportunityItem.GEO_SOURCE_AI
        item.save(update_fields=GEO_FIELDS)
    return items


GEO_FIELDS = [
    'geo_status', 'geo_source', 'geo_area', 'geo_sub_area', 'geo_city', 'geo_confidence', 'geo_basis',
    'geo_error', 'geo_area_location', 'geo_located_at', 'updated_at',
]


def set_manual_location(item, *, area, sub_area='', city='', user=None):
    """Set an item's location by hand and place its area on the map."""
    area, sub_area, city = _text(area, 200), _text(sub_area, 200), _text(city, 100)
    if not area:
        raise ValueError('Enter the area (community or district).')
    item.geo_area_location = area_location_for(item.company, area, city)
    item.geo_area, item.geo_sub_area, item.geo_city = item.geo_area_location.name, sub_area, item.geo_area_location.city
    item.geo_status, item.geo_source = OpportunityItem.GEO_LOCATED, OpportunityItem.GEO_SOURCE_MANUAL
    item.geo_confidence, item.geo_error = None, ''
    item.geo_basis = f'Set by {_user_name(user)}.'
    item.geo_located_at = timezone.now()
    item.save(update_fields=GEO_FIELDS)
    return item


def clear_location(item, *, user=None):
    """Remove an item's location by hand; the AI step will not put one back on its own."""
    item.geo_area = item.geo_sub_area = item.geo_city = item.geo_error = ''
    item.geo_area_location, item.geo_confidence = None, None
    item.geo_status, item.geo_source = OpportunityItem.GEO_UNKNOWN, OpportunityItem.GEO_SOURCE_MANUAL
    item.geo_basis = f'Cleared by {_user_name(user)}.'
    item.geo_located_at = timezone.now()
    item.save(update_fields=GEO_FIELDS)
    return item


def _user_name(user):
    if not user:
        return 'a user'
    return user.get_full_name() or user.get_username()


def parse_location_response(raw_response):
    """{sequence: {'area', 'sub_area', 'city', 'confidence', 'basis'}} from the AI's JSON."""
    parsed = parse_json_object(raw_response)
    entries = parsed.get('items')
    if not isinstance(entries, list):
        raise ValueError('The location AI response has no "items" list.')
    answers = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Each location entry must be a JSON object.')
        try:
            sequence = int(entry.get('sequence'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Location entry has no valid sequence: {entry!r}') from exc
        confidence = entry.get('confidence')
        confidence = 0 if confidence in (None, '') else float(confidence)
        if not 0 <= confidence <= 1:
            raise ValueError('Location confidence must be between 0 and 1.')
        answers[sequence] = {
            'area': _text(entry.get('area'), 200),
            'sub_area': _text(entry.get('sub_area'), 200),
            'city': _text(entry.get('city'), 100),
            'confidence': round(confidence, 4),
            'basis': _text(entry.get('basis'), 2000),
        }
    return answers


def area_location_for(company, area, city):
    """The company's AreaLocation for this area and city (following merges), placed on the
    map if it is new."""
    key = normalize_name(f'{area} {city}')[:200]
    row, created = AreaLocation.objects.get_or_create(
        company=company, normalized_name=key, defaults={'name': area[:200], 'city': city[:100]},
    )
    seen = set()
    while row.merged_into_id and row.pk not in seen:
        seen.add(row.pk)
        row = row.merged_into
    if created or row.status == AreaLocation.STATUS_PENDING:
        place_area(row)
        row.refresh_from_db()
    return row


@transaction.atomic
def merge_areas(company, source_id, target_id):
    """Merge one area into another: its inquiries move to the target, and later results
    with the source's name go to the target too."""
    rows = AreaLocation.objects.select_for_update().in_bulk([source_id, target_id])
    source, target = rows.get(source_id), rows.get(target_id)
    if not source or not target or source.company_id != company.pk or target.company_id != company.pk:
        raise ValueError('Choose two areas of this company.')
    if source.pk == target.pk:
        raise ValueError('Choose a different area to merge into.')
    if target.merged_into_id:
        raise ValueError(f'"{target.name}" was itself merged into another area; merge into that one.')
    moved = OpportunityItem.objects.filter(geo_area_location=source).update(
        geo_area_location=target, geo_area=target.name, geo_city=target.city, updated_at=timezone.now(),
    )
    AreaLocation.objects.filter(merged_into=source).update(merged_into=target)
    source.merged_into = target
    source.save(update_fields=['merged_into', 'updated_at'])
    return moved


def place_area(row, *, use_google=True):
    """Place one area: directory first, then Google. Returns a notice for the user ('' if none).
    Quota or configuration problems leave the area waiting; Google errors are recorded."""
    from apps.real_estate.services.area_map import (
        company_country, directory_index, directory_match, google_place,
    )

    with transaction.atomic():
        row = AreaLocation.objects.select_for_update().get(pk=row.pk)
        if row.status != AreaLocation.STATUS_PENDING and row.status != AreaLocation.STATUS_ERROR:
            return ''
        country = company_country(row.company)
        match = directory_match(directory_index(country), normalize_name(row.name), normalize_name(row.city))
        if match:
            row.status, row.source, row.error = AreaLocation.STATUS_PLACED, AreaLocation.SOURCE_DIRECTORY, ''
            row.latitude, row.longitude, row.matched_label = match.latitude, match.longitude, str(match)
            row.resolved_at = timezone.now()
            row.save()
            return ''
        if not use_google:
            return ''
        return google_place(row, country)


def _sender(opportunity, contact):
    names = [
        opportunity.source_party_name,
        getattr(contact, 'display_name', '') or getattr(contact, 'push_name', ''),
        opportunity.source_contact_detail,
    ]
    return ' / '.join(dict.fromkeys(name for name in names if name)) or 'unknown'


def _linked_address(item):
    if not item.property_id:
        return ''
    address = getattr(item.property, 'address', None)
    if not address:
        return ''
    parts = [address.project_building, address.community, address.city, address.country]
    return ', '.join(part for part in parts if part)


def _text(value, limit):
    return str(value or '').strip()[:limit]
