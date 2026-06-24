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
        'api/internal/whatsapp/session-status/',
        views.internal_session_status,
        name='internal-session-status',
    ),
]
