from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.real_estate.models import Listing, Property, PropertyAddress
from apps.real_estate.services.property_types import resolve_property_type


@transaction.atomic
def promote_candidate(candidate, user, property_data=None, listing_data=None):
    if candidate.review_status != 'pending':
        raise ValidationError('Only pending candidates can be promoted.')
    property_data = dict(property_data or {})
    listing_data = dict(listing_data or {})
    address_data = _only(property_data.pop('address', None) or {}, {
        'country', 'state_region', 'city', 'community', 'project_building',
        'street', 'unit_number', 'postal_code', 'latitude', 'longitude', 'normalized_location',
    })
    property_data = _only(property_data, {
        'reference_code', 'title', 'property_type', 'description', 'bedrooms', 'bathrooms',
        'source_property_type_label',
        'built_up_area', 'plot_area', 'area_unit', 'furnishing', 'completion_status',
        'developer', 'project_name', 'completion_year', 'availability_status', 'assigned_to',
        'market_scope', 'inventory_source_type', 'is_tracked', 'ownership_eligibility',
        'tenure_type', 'attributes',
    })
    listing_data = _only(listing_data, {
        'asking_price', 'currency', 'payment_frequency', 'deposit', 'commission',
        'payment_terms', 'available_from', 'status', 'assigned_agent', 'source_contact',
        'published_at', 'expires_at',
    })
    requested_type = property_data.pop('property_type', None)
    property_type = resolve_property_type(
        candidate.company, requested_type or candidate.property_type, fallback=True,
    )
    property_record = Property(
        company=candidate.company,
        title=property_data.pop('title', candidate.title or f'Property candidate #{candidate.pk}'),
        property_type=property_type,
        source_property_type_label=property_data.pop(
            'source_property_type_label',
            str(candidate.raw_extraction.get('property_type') or ''),
        ),
        description=property_data.pop('description', candidate.description),
        bedrooms=property_data.pop('bedrooms', candidate.bedrooms),
        bathrooms=property_data.pop('bathrooms', candidate.bathrooms),
        built_up_area=property_data.pop('built_up_area', candidate.area),
        area_unit=property_data.pop('area_unit', candidate.area_unit),
        market_scope=property_data.pop('market_scope', candidate.opportunity.market_scope),
        inventory_source_type=property_data.pop(
            'inventory_source_type', candidate.inventory_source_type,
        ),
        is_tracked=property_data.pop('is_tracked', candidate.is_tracked),
        ownership_eligibility=property_data.pop(
            'ownership_eligibility', candidate.ownership_eligibility,
        ),
        tenure_type=property_data.pop('tenure_type', candidate.tenure_type),
        attributes=property_data.pop('attributes', candidate.attributes),
        source='ai_candidate',
        external_source_id=str(candidate.pk),
        **property_data,
    )
    property_record.full_clean()
    property_record.save()
    if address_data or candidate.location_raw:
        address = PropertyAddress(
            company=candidate.company,
            property=property_record,
            normalized_location=candidate.location_raw,
            **(address_data or {}),
        )
        address.full_clean()
        address.save()
    listing_type = 'sale' if candidate.opportunity.activity_type == 'selling' else 'lease'
    asking_price = listing_data.pop('asking_price', candidate.asking_price)
    if asking_price is None:
        raise ValidationError({'asking_price': 'An asking price is required before promotion.'})
    listing = Listing(
        company=candidate.company,
        property=property_record,
        listing_type=listing_type,
        asking_price=asking_price,
        currency=listing_data.pop('currency', candidate.currency),
        payment_frequency=listing_data.pop(
            'payment_frequency', 'not_applicable' if listing_type == 'sale' else 'yearly',
        ),
        source_message=candidate.opportunity.source_message,
        status=listing_data.pop('status', 'draft'),
        is_verified=True,
        **listing_data,
    )
    listing.full_clean()
    listing.save()
    _mark_reviewed(candidate, user, 'promoted', property_record, listing)
    return property_record, listing


@transaction.atomic
def merge_candidate(candidate, listing, user):
    if candidate.review_status != 'pending':
        raise ValidationError('Only pending candidates can be merged.')
    if listing.company_id != candidate.company_id:
        raise ValidationError('The listing must belong to this company.')
    _mark_reviewed(candidate, user, 'merged', listing.property, listing)
    return listing


def reject_candidate(candidate, user):
    if candidate.review_status != 'pending':
        raise ValidationError('Only pending candidates can be rejected.')
    _mark_reviewed(candidate, user, 'rejected')
    return candidate


def _mark_reviewed(candidate, user, status, property_record=None, listing=None):
    candidate.review_status = status
    candidate.promoted_property = property_record
    candidate.promoted_listing = listing
    candidate.reviewed_by = user
    candidate.reviewed_at = timezone.now()
    candidate.full_clean()
    candidate.save(update_fields=[
        'review_status', 'promoted_property', 'promoted_listing',
        'reviewed_by', 'reviewed_at', 'updated_at',
    ])


def _only(values, allowed):
    return {key: value for key, value in values.items() if key in allowed}
