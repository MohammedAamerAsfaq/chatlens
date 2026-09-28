import logging

import requests
from django.conf import settings

from apps.whatsapp_bridge.models import WhatsAppGroup
from .destination_policy import evaluate_destination
from .group_metadata_service import upsert_group_metadata


logger = logging.getLogger(__name__)


def refresh_group_metadata_if_stale(account, destination_jid):
    """Refresh stale group permissions through the connected Baileys session."""
    group = WhatsAppGroup.objects.filter(
        account=account, wa_group_id=destination_jid,
    ).first()
    permission = evaluate_destination(account, destination_jid, group)
    if permission['reason'] not in {'group_metadata_stale', 'group_metadata_unavailable'}:
        return group

    base_url = getattr(settings, 'WORKER_BASE_URL', 'http://localhost:3001').rstrip('/')
    try:
        response = requests.post(
            f'{base_url}/sessions/{account.pk}/destinations/preflight',
            json={'destination_jid': destination_jid},
            headers={'X-Internal-Token': settings.INTERNAL_API_TOKEN},
            timeout=15,
        )
        payload = response.json()
        metadata = payload.get('group_metadata') if response.status_code == 200 else None
        if metadata:
            return upsert_group_metadata(account, metadata)
        logger.warning(
            'group metadata refresh failed | account_id=%s | destination=%s | status=%s | error=%s',
            account.pk, destination_jid, response.status_code, payload.get('error', ''),
        )
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            'group metadata refresh unavailable | account_id=%s | destination=%s | error=%s',
            account.pk, destination_jid, exc,
        )
    return group
