from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, scoped_profiles
from apps.clientpulse.api_reminders import _payload, _queryset
from apps.clientpulse.models import ClientReminderNotification
from apps.clientpulse.services.reminder_windows import local_day_window


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clientpulse_dashboard_view(request):
    if response := denied(request, 'clientpulse.reminders.view'):
        return response
    now = timezone.now(); today_start, tomorrow_start = local_day_window(now)
    reminders = _queryset(request, 'clientpulse.reminders.view')
    active = reminders.filter(status__in=['pending', 'due', 'snoozed'])
    overdue = active.filter(
        Q(status__in=['pending', 'due'], due_at__lt=now)
        | Q(status='snoozed', snoozed_until__lt=now)
    ).count()
    due_today = active.filter(
        Q(status__in=['pending', 'due'], due_at__gte=today_start, due_at__lt=tomorrow_start)
        | Q(status='snoozed', snoozed_until__gte=today_start, snoozed_until__lt=tomorrow_start)
    ).count()
    profile_ids = scoped_profiles(request).values('pk')
    unread = ClientReminderNotification.objects.filter(
        reminder__in=reminders, read_at__isnull=True, dismissed_at__isnull=True,
    ).count()
    return Response({
        'active_clients': profile_ids.count(),
        'overdue_reminders': overdue,
        'due_today': due_today,
        'upcoming': active.filter(
            Q(status__in=['pending', 'due'], due_at__gte=tomorrow_start)
            | Q(status='snoozed', snoozed_until__gte=tomorrow_start)
        ).count(),
        'unread_notifications': unread,
        'unassigned_reminders': active.filter(assigned_to__isnull=True).count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reminder_notifications_view(request):
    if response := denied(request, 'clientpulse.reminders.view'):
        return response
    reminders = _queryset(request, 'clientpulse.reminders.view')
    rows = ClientReminderNotification.objects.filter(
        reminder__in=reminders, dismissed_at__isnull=True,
    ).select_related('reminder__profile__contact', 'recipient__user')[:50]
    return Response([{
        'id': item.pk, 'delivered_at': item.delivered_at, 'read_at': item.read_at,
        'reminder': _payload(item.reminder),
    } for item in rows])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def read_reminder_notification_view(request, notification_id):
    if response := denied(request, 'clientpulse.reminders.view'):
        return response
    reminders = _queryset(request, 'clientpulse.reminders.view')
    notification = ClientReminderNotification.objects.filter(
        pk=notification_id, reminder__in=reminders,
    ).first()
    if not notification:
        return Response({'detail': 'Notification not found.'}, status=404)
    notification.read_at = timezone.now(); notification.save(update_fields=['read_at'])
    return Response({'status': 'read'})
