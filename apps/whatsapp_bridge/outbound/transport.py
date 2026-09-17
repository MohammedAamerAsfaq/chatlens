import requests
from django.conf import settings


def send_to_worker(message):
    base_url = getattr(settings, 'WORKER_BASE_URL', 'http://localhost:3001').rstrip('/')
    response = requests.post(
        f'{base_url}/sessions/{message.whatsapp_account_id}/messages',
        json={
            'outbound_message_id': message.pk,
            'provider_message_id': message.provider_message_id,
            'destination_jid': message.destination_jid,
            'content_type': message.content_type,
            'content': message.content_payload,
            'settings': message.settings_snapshot,
        },
        headers={'X-Internal-Token': settings.INTERNAL_API_TOKEN},
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {'error': response.text[:1000]}
    return response.status_code, payload
