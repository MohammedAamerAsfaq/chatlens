from django.urls import path
from . import views

app_name = 'whatsapp_bridge'

urlpatterns = [
    path(
        'api/internal/whatsapp/message-ingest/',
        views.internal_message_ingest,
        name='internal-message-ingest',
    ),
    path(
        'api/internal/whatsapp/message-ingest-batch/',
        views.internal_message_ingest_batch,
        name='internal-message-ingest-batch',
    ),
    path(
        'api/internal/whatsapp/session-status/',
        views.internal_session_status,
        name='internal-session-status',
    ),
    path(
        'api/internal/whatsapp/contacts-update/',
        views.internal_contacts_update,
        name='internal-contacts-update',
    ),
    path(
        'api/internal/whatsapp/account-settings/<str:session_id>/',
        views.internal_account_settings,
        name='internal-account-settings',
    ),
]
