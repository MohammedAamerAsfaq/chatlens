from dataclasses import dataclass

from django.db import transaction

from apps.clientpulse.models import ClientProfile, ClientPulseSettings
from apps.clientpulse.services.contact_linking import find_exact_contact_ids
from apps.clientpulse.services.profile_service import record_activity
from apps.tenancy.models import CompanyContact, CompanyContactIdentity
from apps.tenancy.services.identity_normalization import normalize_identity


class ConversationConversionError(Exception):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ConversionTarget:
    contact: CompanyContact | None
    profile: ClientProfile | None


def find_conversion_target(whatsapp_contact, company):
    linked = whatsapp_contact.company_contact
    if linked:
        if linked.company_id != company.pk:
            raise ConversationConversionError('cross_company_contact', 'Contact belongs to another company.')
        return ConversionTarget(linked, getattr(linked, 'client_profile', None))

    contact_ids = find_exact_contact_ids(whatsapp_contact)
    if len(contact_ids) > 1:
        raise ConversationConversionError(
            'ambiguous_contact',
            'Multiple company contacts share this identity. Resolve the duplicate before conversion.',
        )
    contact = CompanyContact.objects.filter(company=company, pk__in=contact_ids).first()
    return ConversionTarget(contact, getattr(contact, 'client_profile', None) if contact else None)


def _display_name(whatsapp_contact):
    return (
        whatsapp_contact.display_name or whatsapp_contact.push_name
        or whatsapp_contact.phone_number or whatsapp_contact.wa_contact_id or 'WhatsApp contact'
    )


def _sync_identities(contact, whatsapp_contact):
    identities = [
        (CompanyContactIdentity.TYPE_PHONE, whatsapp_contact.phone_number, True),
        (CompanyContactIdentity.TYPE_WHATSAPP_JID, whatsapp_contact.wa_contact_id, False),
        (CompanyContactIdentity.TYPE_WHATSAPP_JID, whatsapp_contact.lid_jid, False),
    ]
    for identity_type, value, primary in identities:
        normalized = normalize_identity(identity_type, value)
        if not normalized or contact.identities.filter(
            identity_type=identity_type, normalized_value=normalized, is_active=True,
        ).exists():
            continue
        CompanyContactIdentity.objects.create(
            contact=contact, identity_type=identity_type, value=value,
            is_primary=primary, source_type=CompanyContactIdentity.SOURCE_WHATSAPP,
            source_reference=f'whatsapp_contact:{whatsapp_contact.pk}',
        )


@transaction.atomic
def convert_conversation_contact(
    whatsapp_contact, company, actor, lifecycle_stage, *, expected_profile_id=None,
):
    target = find_conversion_target(whatsapp_contact, company)
    contact = target.contact
    if contact and not contact.is_active:
        raise ConversationConversionError('inactive_contact', 'This company contact is archived.')

    if not contact:
        contact = CompanyContact.objects.create(
            company=company, display_name=_display_name(whatsapp_contact),
            category=whatsapp_contact.category, created_by=actor, updated_by=actor,
        )
    elif not contact.display_name:
        contact.display_name = _display_name(whatsapp_contact)
        contact.updated_by = actor
        contact.save(update_fields=['display_name', 'updated_by', 'updated_at'])

    _sync_identities(contact, whatsapp_contact)
    if whatsapp_contact.company_contact_id != contact.pk:
        whatsapp_contact.company_contact = contact
        whatsapp_contact.save(update_fields=['company_contact', 'updated_at'])

    settings, _ = ClientPulseSettings.objects.get_or_create(company=company)
    profile, created = ClientProfile.objects.get_or_create(
        company=company,
        contact=contact,
        defaults={
            'lifecycle_stage': lifecycle_stage,
            'source': 'whatsapp',
            'preferred_channel': 'whatsapp',
            'timezone': settings.default_timezone,
            'preferred_language': settings.default_language,
            'created_by': actor,
            'updated_by': actor,
        },
    )
    if not created and expected_profile_id is None:
        raise ConversationConversionError(
            'conversion_conflict', 'The contact was converted by another request. Please try again.',
        )
    if expected_profile_id and profile.pk != expected_profile_id:
        raise ConversationConversionError(
            'conversion_conflict', 'The linked ClientPulse profile changed. Please refresh and try again.',
        )
    if profile.status == 'archived':
        raise ConversationConversionError('archived_profile', 'This ClientPulse profile is archived.')

    changed = not created and profile.lifecycle_stage != lifecycle_stage
    if changed:
        previous_stage = profile.lifecycle_stage
        profile.lifecycle_stage = lifecycle_stage
        profile.updated_by = actor
        profile.save(update_fields=['lifecycle_stage', 'updated_by', 'updated_at'])
        record_activity(
            profile, actor, 'Lifecycle updated from conversation',
            metadata={'before': previous_stage, 'after': lifecycle_stage},
        )
    elif created:
        record_activity(profile, actor, 'Client created from conversation')

    return profile, created, changed
