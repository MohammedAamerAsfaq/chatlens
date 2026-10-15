from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, ConnectionProvider
from apps.tenancy.services.provider_service import ProviderService
from apps.whatsapp_bridge.models import SessionStatus, WhatsAppAccount


ACCOUNT_NAME = 'Real Estate Mock WhatsApp'


def mock_external_id(company_id):
    return f'real-estate-mock:{company_id}'


def get_mock_account(company):
    return WhatsAppAccount.objects.filter(
        communication_account__company=company,
        communication_account__external_account_id=mock_external_id(company.pk),
    ).first()


def ensure_mock_account(company, owner):
    try:
        provider = ProviderService().default_provider_for_channel('whatsapp')
    except ConnectionProvider.DoesNotExist:
        provider = ConnectionProvider.objects.get(key='baileys')
    communication, _ = CommunicationAccount.objects.get_or_create(
        company=company,
        external_account_id=mock_external_id(company.pk),
        defaults={
            'channel': 'whatsapp', 'provider': provider,
            'name': ACCOUNT_NAME, 'config': {'mock_account': True},
        },
    )
    account, _ = WhatsAppAccount.objects.get_or_create(
        communication_account=communication,
        defaults={
            'owner': owner, 'display_name': ACCOUNT_NAME,
            'phone_number': f'mock-{company.pk}',
            'worker_session_id': mock_external_id(company.pk),
            'session_status': SessionStatus.DISCONNECTED,
            'sync_history': False, 'auto_download_media': False,
            'ai_parsing_enabled': True, 'ai_parsing_enabled_at': timezone.now(),
            'outbound_sending_enabled': False, 'direct_sending_enabled': False,
            'group_sending_enabled': False, 'image_sending_enabled': False,
        },
    )
    changed = []
    for field, value in (
        ('owner', owner), ('display_name', ACCOUNT_NAME), ('is_active', True),
        ('ai_parsing_enabled', True), ('outbound_sending_enabled', False),
        ('direct_sending_enabled', False), ('group_sending_enabled', False),
        ('image_sending_enabled', False),
    ):
        if getattr(account, field) != value:
            setattr(account, field, value)
            changed.append(field)
    if not account.ai_parsing_enabled_at:
        account.ai_parsing_enabled_at = timezone.now()
        changed.append('ai_parsing_enabled_at')
    if changed:
        account.save(update_fields=[*changed, 'updated_at'])
    return account
