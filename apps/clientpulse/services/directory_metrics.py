from django.db.models import Case, DateTimeField, F, OuterRef, Subquery, When
from django.db.models.functions import Greatest

from apps.clientpulse.models import ClientReminder
from apps.whatsapp_bridge.models import MessageDirection, WhatsAppMessage


ACTIVE_REMINDER_STATUSES = ('pending', 'due', 'snoozed')


def _latest_message_time(queryset):
    return Subquery(
        queryset.order_by('-message_time', '-pk').values('message_time')[:1],
        output_field=DateTimeField(),
    )


def with_directory_metrics(queryset):
    """Attach live communication and reminder timestamps to client rows."""
    messages = WhatsAppMessage.objects.filter(
        account__communication_account__company_id=OuterRef('company_id'),
    )
    direct_messages = messages.filter(
        contact__company_contact_id=OuterRef('contact_id'),
    )
    chat_messages = messages.filter(
        chat__contact__company_contact_id=OuterRef('contact_id'),
    )
    direct_replies = direct_messages.filter(direction=MessageDirection.INBOUND)
    chat_replies = chat_messages.filter(direction=MessageDirection.INBOUND)
    reminders = ClientReminder.objects.filter(
        profile_id=OuterRef('pk'),
        status__in=ACTIVE_REMINDER_STATUSES,
    ).annotate(
        effective_due_at=Case(
            When(
                status='snoozed', snoozed_until__isnull=False,
                then=F('snoozed_until'),
            ),
            default=F('due_at'),
            output_field=DateTimeField(),
        ),
    ).order_by('effective_due_at', 'pk')
    return queryset.annotate(
        system_last_contact_at=Greatest(
            _latest_message_time(direct_messages),
            _latest_message_time(chat_messages),
            output_field=DateTimeField(),
        ),
        system_last_replied_at=Greatest(
            _latest_message_time(direct_replies),
            _latest_message_time(chat_replies),
            output_field=DateTimeField(),
        ),
        system_next_follow_up_at=Subquery(
            reminders.values('effective_due_at')[:1],
            output_field=DateTimeField(),
        ),
    )
