import logging
from django.utils.dateparse import parse_datetime
from ..models import WhatsAppAccount, SessionStatus, SyncLog

logger = logging.getLogger(__name__)


class SessionService:

    def update_session_status(self, payload: dict) -> WhatsAppAccount:
        worker_session_id = payload['worker_session_id']
        status = payload['status']
        event_time = parse_datetime(payload.get('event_time', '')) if payload.get('event_time') else None

        account = WhatsAppAccount.objects.get(worker_session_id=worker_session_id)

        update_fields = {'session_status': status}

        if payload.get('phone_number'):
            update_fields['phone_number'] = payload['phone_number']
        if payload.get('display_name'):
            update_fields['display_name'] = payload['display_name']
        if status == SessionStatus.CONNECTED and event_time:
            update_fields['last_connected_at'] = event_time
        if status in (SessionStatus.DISCONNECTED, SessionStatus.LOGGED_OUT) and event_time:
            update_fields['last_disconnected_at'] = event_time

        WhatsAppAccount.objects.filter(pk=account.pk).update(**update_fields)
        account.refresh_from_db()

        SyncLog.objects.create(
            account=account,
            event_type='session_status',
            status=status,
            metadata=payload,
        )

        logger.info(
            f"Session status updated | account={account.pk} | status={status}"
        )
        return account
