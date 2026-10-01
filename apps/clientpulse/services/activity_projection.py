from django.db import transaction

from apps.clientpulse.models import ClientActivity, ClientProfile
from apps.queue_management.services import enqueue_task


def enqueue_message_projection(message):
    company_contact_id = getattr(message.contact, 'company_contact_id', None)
    if not company_contact_id:
        return None
    profile = ClientProfile.objects.select_related('company').filter(
        contact_id=company_contact_id,
    ).first()
    if not profile:
        return None
    return enqueue_task(
        task_key='clientpulse.project_activity', queue_name='clientpulse',
        payload={'version': 1, 'company_id': profile.company_id, 'message_id': message.pk},
        idempotency_key=f'clientpulse:message-activity:{message.pk}',
        correlation_id=f'whatsapp-message:{message.pk}', company=profile.company,
    )


@transaction.atomic
def project_message_activity(message_id, company_id):
    from apps.whatsapp_bridge.models import WhatsAppMessage

    message = WhatsAppMessage.objects.select_related('contact').get(pk=message_id)
    company_contact_id = getattr(message.contact, 'company_contact_id', None)
    profile = ClientProfile.objects.select_for_update().get(
        company_id=company_id, contact_id=company_contact_id,
    )
    activity, created = ClientActivity.objects.get_or_create(
        company_id=company_id, profile=profile,
        source_model='whatsapp_message', source_id=str(message.pk),
        defaults={
            'activity_type': f'{message.direction}_message',
            'occurred_at': message.message_time,
            'title': f'{message.direction.title()} WhatsApp message',
            'channel': 'whatsapp', 'direction': message.direction,
            'metadata': {'message_id': message.pk, 'message_type': message.message_type},
        },
    )
    update_fields = []
    if message.direction == 'inbound' and (
        profile.last_inbound_at is None or message.message_time > profile.last_inbound_at
    ):
        profile.last_inbound_at = message.message_time; update_fields.append('last_inbound_at')
    if profile.last_contacted_at is None or message.message_time > profile.last_contacted_at:
        profile.last_contacted_at = message.message_time; update_fields.append('last_contacted_at')
    if update_fields:
        profile.save(update_fields=[*update_fields, 'updated_at'])
    return {'activity_id': activity.pk, 'created': created, 'profile_id': profile.pk}
