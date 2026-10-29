"""Prepare raw or AI-structured Real Estate opportunity searches."""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from apps.real_estate.models import ActivityType, RealEstateAgentCallLog, RealEstatePromptConfig
from apps.real_estate.services.agent_call import call_real_estate_agent
from apps.real_estate.services.opportunity_search_query import build_constraints, parse_constraints
from apps.real_estate.services.prompts import configured_prompt
from apps.real_estate.services.response_parser import parse_json_object


SEARCH_MODE_HYBRID = 'hybrid'
SEARCH_MODE_STRUCTURED = 'structured'
SEARCH_MODES = {SEARCH_MODE_HYBRID, SEARCH_MODE_STRUCTURED}


@dataclass(frozen=True)
class OpportunitySearchPlan:
    mode: str
    embedding_query: str
    constraints: object
    interpretation: dict | None = None


def prepare_opportunity_search(*, company, activity_type, query, mode=SEARCH_MODE_HYBRID):
    query = (query or '').strip()
    if activity_type not in {value for value, _label in ActivityType.choices}:
        raise ValueError('A valid Real Estate activity type is required.')
    if mode not in SEARCH_MODES:
        raise ValueError('Search mode must be hybrid or structured.')
    if mode == SEARCH_MODE_HYBRID or not query:
        return OpportunitySearchPlan(mode, query, parse_constraints(query, company))

    prompt, prompt_config = configured_prompt(
        company, RealEstatePromptConfig.KEY_SEARCH_STRUCTURING,
    )
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json.dumps({
            'activity_type': activity_type,
            'search_phrase': query,
        })},
    ]
    raw = call_real_estate_agent(
        purpose=RealEstateAgentCallLog.PURPOSE_SEARCH_STRUCTURING,
        messages=messages,
        company=company,
        prompt_config=prompt_config,
        correlation_id=f'opportunity-search:{uuid4().hex}',
        temperature=0,
    )
    interpretation = _validate_structure(parse_json_object(raw))
    canonical = _canonical_query(interpretation)
    if not canonical:
        raise ValueError('The AI did not identify any searchable property details.')
    constraints = build_constraints(
        query=canonical,
        company=company,
        property_types=interpretation['property_types'],
        bedrooms_min=interpretation['bedrooms_min'],
        bedrooms_max=interpretation['bedrooms_max'],
        amount_min=interpretation['amount_min'],
        amount_max=interpretation['amount_max'],
    )
    public_interpretation = {
        **interpretation,
        'bedrooms_min': _json_number(interpretation['bedrooms_min']),
        'bedrooms_max': _json_number(interpretation['bedrooms_max']),
        'amount_min': _json_number(interpretation['amount_min']),
        'amount_max': _json_number(interpretation['amount_max']),
        'canonical_query': canonical,
    }
    return OpportunitySearchPlan(mode, canonical, constraints, public_interpretation)


def _validate_structure(value):
    if not isinstance(value, dict):
        raise ValueError('The AI search structure must be a JSON object.')
    structured = {
        'property_types': _string_list(value.get('property_types')),
        'locations': _string_list(value.get('locations')),
        'bedrooms_min': _decimal(value.get('bedrooms_min'), 'bedrooms_min'),
        'bedrooms_max': _decimal(value.get('bedrooms_max'), 'bedrooms_max'),
        'amount_min': _decimal(value.get('amount_min'), 'amount_min'),
        'amount_max': _decimal(value.get('amount_max'), 'amount_max'),
        'currency': str(value.get('currency') or '').strip().upper()[:3],
        'amenities': _string_list(value.get('amenities')),
        'keywords': _string_list(value.get('keywords')),
    }
    _validate_range(structured, 'bedrooms')
    _validate_range(structured, 'amount')
    return structured


def _string_list(value):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:20] if str(item).strip()]


def _decimal(value, field):
    if value in (None, ''):
        return None
    try:
        number = Decimal(str(value).replace(',', ''))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'AI returned an invalid {field}.') from exc
    if number < 0:
        raise ValueError(f'AI returned a negative {field}.')
    return number


def _validate_range(value, prefix):
    minimum, maximum = value[f'{prefix}_min'], value[f'{prefix}_max']
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(f'AI returned an invalid {prefix} range.')


def _canonical_query(value):
    parts = [*value['property_types'], *value['locations']]
    parts.extend(_range_parts(value, 'bedrooms', 'bedrooms'))
    amount = _range_parts(value, 'amount', value['currency'] or 'price')
    parts.extend(amount)
    parts.extend(value['amenities'])
    parts.extend(value['keywords'])
    return '; '.join(dict.fromkeys(part for part in parts if part))


def _range_parts(value, prefix, label):
    minimum, maximum = value[f'{prefix}_min'], value[f'{prefix}_max']
    if minimum is None and maximum is None:
        return []
    if minimum == maximum:
        return [f'{minimum} {label}']
    return [f'{minimum or "any"} to {maximum or "any"} {label}']


def _json_number(value):
    if value is None:
        return None
    return int(value) if value == value.to_integral_value() else float(value)
