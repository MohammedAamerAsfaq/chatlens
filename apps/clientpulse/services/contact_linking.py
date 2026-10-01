from dataclasses import dataclass
from itertools import combinations

from django.db import transaction
from django.db.models import Count

from apps.clientpulse.models import ContactMergeCandidate
from apps.tenancy.models import CompanyContactIdentity
from apps.tenancy.services.identity_normalization import (
    normalize_identity,
    phone_from_whatsapp_jid,
)


@dataclass(frozen=True)
class ContactLinkResult:
    status: str
    contact_id: int | None = None
    candidate_count: int = 0


def _account_company_id(whatsapp_contact):
    communication_account = whatsapp_contact.account.communication_account
    return communication_account.company_id if communication_account else None


def _lookup_keys(whatsapp_contact):
    keys = set()
    for jid in (whatsapp_contact.wa_contact_id, whatsapp_contact.lid_jid):
        normalized = normalize_identity(CompanyContactIdentity.TYPE_WHATSAPP_JID, jid)
        if normalized:
            keys.add((CompanyContactIdentity.TYPE_WHATSAPP_JID, normalized))
        phone = phone_from_whatsapp_jid(jid)
        if phone:
            keys.add((CompanyContactIdentity.TYPE_PHONE, phone))
    phone = normalize_identity(
        CompanyContactIdentity.TYPE_PHONE, whatsapp_contact.phone_number,
    )
    if phone:
        keys.add((CompanyContactIdentity.TYPE_PHONE, phone))
    return keys


def find_exact_contact_ids(whatsapp_contact):
    company_id = _account_company_id(whatsapp_contact)
    if not company_id:
        return set()
    contact_ids = set()
    for identity_type, normalized_value in _lookup_keys(whatsapp_contact):
        matches = CompanyContactIdentity.objects.filter(
            company_id=company_id,
            identity_type=identity_type,
            normalized_value=normalized_value,
            is_active=True,
            contact__is_active=True,
        ).values_list('contact_id', flat=True)
        contact_ids.update(matches)
    return contact_ids


def _record_ambiguity(company_id, contact_ids, whatsapp_contact):
    reasons = [{
        'type': 'whatsapp_exact_identity_collision',
        'whatsapp_contact_id': whatsapp_contact.pk,
    }]
    created = 0
    for left_id, right_id in combinations(sorted(contact_ids), 2):
        _, was_created = ContactMergeCandidate.objects.get_or_create(
            company_id=company_id,
            left_contact_id=left_id,
            right_contact_id=right_id,
            defaults={'match_reasons': reasons, 'confidence': 1},
        )
        created += int(was_created)
    return created


def generate_identity_merge_candidates(company_id, *, apply=False):
    """Find exact shared identities; never merge contacts automatically."""
    collisions = CompanyContactIdentity.objects.filter(
        company_id=company_id,
        is_active=True,
        contact__is_active=True,
    ).values('identity_type', 'normalized_value').annotate(
        contact_count=Count('contact_id', distinct=True),
    ).filter(contact_count__gt=1)
    pairs = set()
    for collision in collisions.iterator():
        contact_ids = CompanyContactIdentity.objects.filter(
            company_id=company_id,
            identity_type=collision['identity_type'],
            normalized_value=collision['normalized_value'],
            is_active=True,
        ).values_list('contact_id', flat=True).distinct()
        for left_id, right_id in combinations(sorted(contact_ids), 2):
            pairs.add((left_id, right_id, collision['identity_type']))
    if apply:
        for left_id, right_id, identity_type in pairs:
            ContactMergeCandidate.objects.get_or_create(
                company_id=company_id,
                left_contact_id=left_id,
                right_contact_id=right_id,
                defaults={
                    'match_reasons': [{'type': 'shared_exact_identity', 'identity_type': identity_type}],
                    'confidence': 1,
                },
            )
    return len(pairs)


@transaction.atomic
def link_whatsapp_contact(whatsapp_contact, *, apply=False):
    company_id = _account_company_id(whatsapp_contact)
    if not company_id:
        return ContactLinkResult('missing_company')
    if whatsapp_contact.company_contact_id:
        if whatsapp_contact.company_contact.company_id != company_id:
            return ContactLinkResult('cross_company_link')
        return ContactLinkResult('already_linked', whatsapp_contact.company_contact_id)

    contact_ids = find_exact_contact_ids(whatsapp_contact)
    if not contact_ids:
        return ContactLinkResult('unmatched')
    if len(contact_ids) > 1:
        created = _record_ambiguity(company_id, contact_ids, whatsapp_contact) if apply else 0
        return ContactLinkResult('ambiguous', candidate_count=created)

    contact_id = next(iter(contact_ids))
    if apply:
        whatsapp_contact.company_contact_id = contact_id
        whatsapp_contact.save(update_fields=['company_contact_id', 'updated_at'])
    return ContactLinkResult('linked' if apply else 'would_link', contact_id)


def unlink_whatsapp_contact(whatsapp_contact, *, company_id):
    if _account_company_id(whatsapp_contact) != company_id:
        raise ValueError('WhatsApp contact does not belong to this company.')
    whatsapp_contact.company_contact = None
    whatsapp_contact.save(update_fields=['company_contact_id', 'updated_at'])
