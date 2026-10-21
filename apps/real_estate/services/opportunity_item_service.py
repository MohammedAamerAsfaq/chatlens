from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.real_estate.models import ActivityType, OpportunityItem, Property, PropertyAddress


@transaction.atomic
def link_item(item, property_record, user):
    item = OpportunityItem.objects.select_for_update().get(pk=item.pk)
    if property_record.company_id != item.company_id:
        raise ValidationError('The property must belong to this company.')
    item.property = property_record
    item.match_status = OpportunityItem.MATCH_LINKED
    item.match_confidence = 1
    item.link_method = OpportunityItem.LINK_MANUAL
    item.linked_by = user
    item.linked_at = timezone.now()
    item.full_clean()
    item.save(update_fields=_link_fields())
    return item


@transaction.atomic
def unlink_item(item):
    item = OpportunityItem.objects.select_for_update().get(pk=item.pk)
    item.property = None
    item.match_status = OpportunityItem.MATCH_UNMATCHED
    item.match_confidence = None
    item.link_method = OpportunityItem.LINK_NONE
    item.linked_by = None
    item.linked_at = None
    item.save(update_fields=_link_fields())
    return item


@transaction.atomic
def create_property_from_item(item, user):
    # Lock only the item row. Joining nullable property fields causes PostgreSQL
    # to reject SELECT FOR UPDATE against the nullable side of the outer join.
    item = OpportunityItem.objects.select_for_update().select_related(
        'opportunity',
    ).get(pk=item.pk)
    if item.opportunity.activity_type not in ActivityType.offer_values():
        raise ValidationError('Only a selling or leasing offer can create a physical property.')
    if item.property_id and item.match_status == OpportunityItem.MATCH_LINKED:
        raise ValidationError('This opportunity item is already linked to a property.')
    if not item.property_type_id:
        raise ValidationError({'property_type': 'Review and select a property type first.'})
    property_record = Property(
        company=item.company,
        title=item.title or f'Property from opportunity #{item.opportunity_id}',
        property_type=item.property_type,
        source_property_type_label=item.property_type_label,
        market_scope=item.opportunity.market_scope,
        inventory_source_type='floating',
        ownership_eligibility=item.ownership_eligibility,
        tenure_type=item.tenure_type,
        attributes=item.attributes,
        description=item.description or item.opportunity.original_message,
        bedrooms=item.bedrooms_min if item.bedrooms_min == item.bedrooms_max else None,
        bathrooms=item.bathrooms_min if item.bathrooms_min == item.bathrooms_max else None,
        built_up_area=item.area_min if item.area_min == item.area_max else None,
        area_unit=item.area_unit,
        furnishing=item.furnishing,
        availability_status='draft',
        assigned_to=item.opportunity.assigned_to,
        source='opportunity_item',
        external_source_id=str(item.pk),
    )
    property_record.full_clean()
    property_record.save()
    if item.location_raw:
        address = PropertyAddress(
            company=item.company, property=property_record,
            normalized_location=item.location_raw,
        )
        address.full_clean()
        address.save()
    return link_item(item, property_record, user), property_record


def _link_fields():
    return [
        'property', 'match_status', 'match_confidence', 'link_method',
        'linked_by', 'linked_at', 'updated_at',
    ]
