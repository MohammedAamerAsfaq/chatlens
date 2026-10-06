from django.urls import path

from .api_clients import (
    activate_client_view, archive_client_view, client_detail_view, clients_view,
    deactivate_client_view,
)
from .api_engagement import (
    client_consents_view, client_note_detail_view, client_notes_view, client_timeline_view,
)
from .api_identities import client_identities_view, client_identity_detail_view
from .api_follow_up import manual_follow_up_view
from .api_dashboard import (
    clientpulse_dashboard_view, read_reminder_notification_view, reminder_notifications_view,
)
from .api_reminders import (
    cancel_reminder_view, complete_reminder_view, reminder_detail_view,
    reminders_view, snooze_reminder_view,
)
from .api_reference import client_options_view, client_tags_view, clientpulse_settings_view
from .api_conversion import conversation_contact_candidates_view, convert_conversation_contact_view

urlpatterns = [
    path('clientpulse/clients/', clients_view, name='clientpulse-clients'),
    path(
        'clientpulse/conversation-contacts/<int:whatsapp_contact_id>/convert/',
        convert_conversation_contact_view,
        name='clientpulse-conversation-contact-convert',
    ),
    path(
        'clientpulse/conversation-contacts/',
        conversation_contact_candidates_view,
        name='clientpulse-conversation-contact-candidates',
    ),
    path('clientpulse/clients/<int:profile_id>/', client_detail_view, name='clientpulse-client-detail'),
    path('clientpulse/clients/<int:profile_id>/deactivate/', deactivate_client_view, name='clientpulse-client-deactivate'),
    path('clientpulse/clients/<int:profile_id>/activate/', activate_client_view, name='clientpulse-client-activate'),
    path('clientpulse/clients/<int:profile_id>/archive/', archive_client_view, name='clientpulse-client-archive'),
    path('clientpulse/clients/<int:profile_id>/timeline/', client_timeline_view, name='clientpulse-client-timeline'),
    path('clientpulse/clients/<int:profile_id>/follow-up/', manual_follow_up_view, name='clientpulse-manual-follow-up'),
    path('clientpulse/clients/<int:profile_id>/notes/', client_notes_view, name='clientpulse-client-notes'),
    path('clientpulse/clients/<int:profile_id>/consents/', client_consents_view, name='clientpulse-client-consents'),
    path('clientpulse/clients/<int:profile_id>/identities/', client_identities_view, name='clientpulse-client-identities'),
    path('clientpulse/clients/<int:profile_id>/identities/<int:identity_id>/', client_identity_detail_view, name='clientpulse-client-identity-detail'),
    path('clientpulse/notes/<int:note_id>/', client_note_detail_view, name='clientpulse-note-detail'),
    path('clientpulse/tags/', client_tags_view, name='clientpulse-tags'),
    path('clientpulse/options/', client_options_view, name='clientpulse-options'),
    path('clientpulse/settings/', clientpulse_settings_view, name='clientpulse-settings'),
    path('clientpulse/dashboard/', clientpulse_dashboard_view, name='clientpulse-dashboard'),
    path('clientpulse/reminders/', reminders_view, name='clientpulse-reminders'),
    path('clientpulse/reminders/<int:reminder_id>/', reminder_detail_view, name='clientpulse-reminder-detail'),
    path('clientpulse/reminders/<int:reminder_id>/complete/', complete_reminder_view, name='clientpulse-reminder-complete'),
    path('clientpulse/reminders/<int:reminder_id>/snooze/', snooze_reminder_view, name='clientpulse-reminder-snooze'),
    path('clientpulse/reminders/<int:reminder_id>/cancel/', cancel_reminder_view, name='clientpulse-reminder-cancel'),
    path('clientpulse/notifications/', reminder_notifications_view, name='clientpulse-notifications'),
    path('clientpulse/notifications/<int:notification_id>/read/', read_reminder_notification_view, name='clientpulse-notification-read'),
]
