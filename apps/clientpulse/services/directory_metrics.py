from django.db.models import Case, DateTimeField, F, OuterRef, Q, Subquery, When

from apps.clientpulse.models import ClientReminder
from apps.whatsapp_bridge.models import MessageDirection, WhatsAppMessage


ACTIVE_REMINDER_STATUSES = ('pending', 'due', 'snoozed')


def with_directory_metrics(queryset):
    """Attach live communication and reminder timestamps to client rows."""
    messages = WhatsAppMessage.objects.filter(
        account__communication_account__company_id=OuterRef('company_id'),
    ).filter(
        Q(contact__company_contact_id=OuterRef('contact_id'))
        | Q(chat__contact__company_contact_id=OuterRef('contact_id')),
    )
    latest_message = messages.order_by('-message_time', '-pk')
    latest_reply = messages.filter(
        direction=MessageDirection.INBOUND,
    ).order_by('-message_time', '-pk')
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
        system_last_contact_at=Subquery(
            latest_message.values('message_time')[:1],
            output_field=DateTimeField(),
        ),
        system_last_replied_at=Subquery(
            latest_reply.values('message_time')[:1],
            output_field=DateTimeField(),
        ),
        system_next_follow_up_at=Subquery(
            reminders.values('effective_due_at')[:1],
            output_field=DateTimeField(),
        ),
    )
