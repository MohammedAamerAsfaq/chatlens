from django.db import transaction
from django.utils import timezone

from apps.clientpulse.models import ClientActivity, ClientTag, ClientTagAssignment
from apps.tenancy.models import CompanyContact, CompanyContactIdentity


CONTACT_FIELDS = (
    'contact_type', 'first_name', 'middle_name', 'last_name',
    'display_name', 'legal_name', 'category', 'notes',
)
PROFILE_FIELDS = (
    'owner', 'lifecycle_stage', 'status', 'priority', 'source',
    'preferred_channel', 'preferred_language', 'timezone',
    'last_contacted_at', 'last_inbound_at', 'next_follow_up_at',
    'do_not_contact', 'do_not_contact_reason',
)


def record_activity(profile, actor, title, *, summary='', metadata=None, activity_type='status_change'):
    return ClientActivity.objects.create(
        company=profile.company, profile=profile, activity_type=activity_type,
        occurred_at=timezone.now(), title=title, summary=summary,
        metadata=metadata or {}, created_by=actor,
    )


def replace_tags(profile, tag_ids, actor):
    valid_ids = set(ClientTag.objects.filter(
        company=profile.company, is_active=True, pk__in=tag_ids,
    ).values_list('pk', flat=True))
    if valid_ids != set(tag_ids):
        raise ValueError('Tags must belong to the client company.')
    profile.tag_assignments.exclude(tag_id__in=tag_ids).delete()
    existing = set(profile.tag_assignments.values_list('tag_id', flat=True))
    ClientTagAssignment.objects.bulk_create([
        ClientTagAssignment(
            company=profile.company, profile=profile, tag_id=tag_id, assigned_by=actor,
        ) for tag_id in valid_ids if tag_id not in existing
    ])


@transaction.atomic
def create_profile(company, actor, contact_data, profile_data, identities, tag_ids):
    contact = CompanyContact.objects.create(
        company=company, created_by=actor, updated_by=actor, **contact_data,
    )
    for item in identities:
        CompanyContactIdentity.objects.create(
            contact=contact,
            identity_type=item['identity_type'], value=item['value'],
            label=item.get('label', ''), is_primary=item.get('is_primary', False),
            source_type=CompanyContactIdentity.SOURCE_MANUAL,
        )
    from apps.clientpulse.models import ClientProfile
    profile = ClientProfile.objects.create(
        company=company, contact=contact, created_by=actor, updated_by=actor, **profile_data,
    )
    replace_tags(profile, tag_ids, actor)
    record_activity(profile, actor, 'Client profile created')
    return profile


@transaction.atomic
def update_profile(profile, actor, contact_data, profile_data, tag_ids=None):
    before = {
        'profile': {field: getattr(profile, f'{field}_id' if field == 'owner' else field) for field in profile_data},
        'contact': {field: getattr(profile.contact, field) for field in contact_data},
    }
    for field, value in contact_data.items():
        setattr(profile.contact, field, value)
    profile.contact.updated_by = actor
    profile.contact.save()
    for field, value in profile_data.items():
        setattr(profile, field, value)
    profile.updated_by = actor
    profile.save()
    if tag_ids is not None:
        replace_tags(profile, tag_ids, actor)
    after = {
        'profile': {field: getattr(profile, f'{field}_id' if field == 'owner' else field) for field in profile_data},
        'contact': {field: getattr(profile.contact, field) for field in contact_data},
    }
    if before != after or tag_ids is not None:
        record_activity(profile, actor, 'Client profile updated', metadata={'before': before, 'after': after})
    return profile
