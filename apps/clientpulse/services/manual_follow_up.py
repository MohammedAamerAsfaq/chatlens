from apps.clientpulse.models import ClientActivity, ClientPulseSettings, ContactConsent
from apps.whatsapp_bridge.models import OutboundAsset, WhatsAppContact
from apps.whatsapp_bridge.outbound.message_service import create_outbound_message


def _consent_decision(profile):
    settings, _ = ClientPulseSettings.objects.get_or_create(company=profile.company)
    consent = ContactConsent.objects.filter(
        company=profile.company, profile=profile,
        channel='whatsapp', purpose='follow_up',
    ).first()
    status = consent.status if consent else 'unknown'
    if settings.consent_mode == 'enforced' and status != 'granted':
        raise ValueError(f'follow_up_consent_{status}')
    return {'mode': settings.consent_mode, 'status': status}


def _validate_profile(profile):
    if profile.status != 'active' or profile.lifecycle_stage == 'blocked':
        raise ValueError('client_not_active')
    if profile.do_not_contact:
        raise ValueError('client_do_not_contact')


def _linked_contact(profile, contact_id):
    contact = WhatsAppContact.objects.select_related(
        'account__communication_account',
    ).filter(
        pk=contact_id, company_contact=profile.contact,
        account__communication_account__company=profile.company,
    ).first()
    if not contact:
        raise ValueError('whatsapp_contact_not_linked')
    if not contact.wa_contact_id or '@' not in contact.wa_contact_id:
        raise ValueError('whatsapp_destination_invalid')
    return contact


def queue_manual_follow_up(*, profile, actor, contact_id, text, asset_id=None,
                           idempotency_key, confirm_new_chat=False):
    _validate_profile(profile)
    consent = _consent_decision(profile)
    contact = _linked_contact(profile, contact_id)
    asset = None
    if asset_id:
        asset = OutboundAsset.objects.filter(pk=asset_id, company=profile.company).first()
        if not asset:
            raise ValueError('outbound_asset_not_found')
    outbound, created = create_outbound_message(
        account=contact.account, destination_jid=contact.wa_contact_id,
        text=text, requested_by=actor, asset=asset,
        idempotency_key=f'clientpulse:{profile.pk}:{idempotency_key}',
        confirm_new_chat=confirm_new_chat,
    )
    title = 'Manual WhatsApp follow-up queued'
    if outbound.status == outbound.STATUS_BLOCKED:
        title = 'Manual WhatsApp follow-up blocked'
    ClientActivity.objects.get_or_create(
        company=profile.company, profile=profile,
        source_model='outbound_message', source_id=str(outbound.pk),
        defaults={
            'activity_type': 'outbound_message',
            'occurred_at': outbound.requested_at,
            'title': title,
            'channel': 'whatsapp', 'direction': 'outbound',
            'metadata': {
                'outbound_message_id': outbound.pk,
                'consent_mode': consent['mode'],
                'consent_status': consent['status'],
            },
            'created_by': actor,
        },
    )
    return outbound, created, consent
