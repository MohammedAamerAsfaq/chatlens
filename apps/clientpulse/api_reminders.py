from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none
from apps.clientpulse.models import ClientReminder
from apps.clientpulse.serializers import ClientReminderInputSerializer, SnoozeInputSerializer
from apps.clientpulse.services.profile_service import record_activity
from apps.clientpulse.services.reminder_service import complete_reminder, snooze_reminder
from apps.clientpulse.services.reminder_windows import local_day_window
from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from apps.tenancy.services.authorization import permission_scope


def _queryset(request, permission_code):
    company = default_company_for_user(request.user)
    queryset = ClientReminder.objects.filter(company=company).select_related(
        'profile__contact', 'assigned_to__user', 'completed_by',
    )
    scope = permission_scope(request.user, permission_code, company)
    membership = active_membership_for_user(request.user)
    if scope == 'all':
        return queryset
    if scope == 'assigned' and membership:
        return queryset.filter(Q(assigned_to=membership) | Q(profile__owner=membership))
    if scope == 'own':
        return queryset.filter(Q(created_by=request.user) | Q(assigned_to=membership))
    return queryset.none()


def _payload(reminder):
    return {
        'id': reminder.pk, 'profile': {
            'id': reminder.profile_id,
            'display_name': reminder.profile.contact.display_name or reminder.profile.contact.legal_name,
        },
        'assigned_to': None if not reminder.assigned_to else {
            'id': reminder.assigned_to_id, 'username': reminder.assigned_to.user.username,
        },
        'title': reminder.title, 'description': reminder.description,
        'due_at': reminder.due_at, 'timezone': reminder.timezone,
        'priority': reminder.priority, 'status': reminder.status,
        'recurrence_type': reminder.recurrence_type,
        'recurrence_rule': reminder.recurrence_rule,
        'snoozed_until': reminder.snoozed_until,
        'completed_at': reminder.completed_at,
        'next_occurrence_at': reminder.next_occurrence_at,
        'occurrence_number': reminder.occurrence_number,
    }


def _assignee(company, assignee_id):
    if assignee_id is None:
        return None
    return CompanyMembership.objects.filter(
        company=company, pk=assignee_id, is_active=True,
    ).first()


class ReminderPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reminders_view(request):
    permission = 'clientpulse.reminders.view' if request.method == 'GET' else 'clientpulse.reminders.manage'
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    if request.method == 'POST':
        serializer = ClientReminderInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        data = serializer.validated_data
        profile = profile_or_none(request, data.pop('profile_id'), permission)
        if not profile:
            return Response({'detail': 'Client not found.'}, status=404)
        assignee = _assignee(company, data.pop('assigned_to_id', None))
        if request.data.get('assigned_to_id') and not assignee:
            return Response({'assigned_to_id': ['Invalid company member.']}, status=400)
        scope = permission_scope(request.user, permission, company)
        membership = active_membership_for_user(request.user)
        if scope != 'all' and assignee not in (None, membership):
            return Response({'assigned_to_id': ['You may only assign reminders to yourself.']}, status=403)
        reminder = ClientReminder.objects.create(
            company=company, profile=profile, assigned_to=assignee or membership,
            created_by=request.user, **data,
        )
        record_activity(profile, request.user, 'Reminder created', metadata={'reminder_id': reminder.pk})
        return Response(_payload(reminder), status=201)

    queryset = _queryset(request, permission)
    now = timezone.now(); today_start, tomorrow_start = local_day_window(now)
    window = request.query_params.get('window', '')
    if window == 'overdue':
        queryset = queryset.filter(Q(status__in=['pending', 'due'], due_at__lt=now) | Q(status='snoozed', snoozed_until__lt=now))
    elif window == 'today':
        queryset = queryset.filter(
            Q(status__in=['pending', 'due'], due_at__gte=today_start, due_at__lt=tomorrow_start)
            | Q(status='snoozed', snoozed_until__gte=today_start, snoozed_until__lt=tomorrow_start)
        )
    elif window == 'upcoming':
        queryset = queryset.filter(
            Q(status='pending', due_at__gte=tomorrow_start)
            | Q(status='snoozed', snoozed_until__gte=tomorrow_start)
        )
    elif window == 'completed':
        queryset = queryset.filter(status='completed')
    elif status_value := request.query_params.get('status'):
        queryset = queryset.filter(status=status_value)
    if profile_id := request.query_params.get('profile_id'):
        queryset = queryset.filter(profile_id=profile_id)
    if assigned_to_id := request.query_params.get('assigned_to_id'):
        queryset = queryset.filter(assigned_to_id=assigned_to_id)
    paginator = ReminderPagination(); page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([_payload(item) for item in page])


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def reminder_detail_view(request, reminder_id):
    if response := denied(request, 'clientpulse.reminders.manage'):
        return response
    reminder = _queryset(request, 'clientpulse.reminders.manage').filter(pk=reminder_id).first()
    if not reminder:
        return Response({'detail': 'Reminder not found.'}, status=404)
    serializer = ClientReminderInputSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = serializer.validated_data
    if 'assigned_to_id' in data:
        assignee = _assignee(reminder.company, data.pop('assigned_to_id'))
        if request.data.get('assigned_to_id') and not assignee:
            return Response({'assigned_to_id': ['Invalid company member.']}, status=400)
        membership = active_membership_for_user(request.user)
        if permission_scope(request.user, 'clientpulse.reminders.manage') != 'all' and assignee not in (None, membership):
            return Response({'assigned_to_id': ['You may only assign reminders to yourself.']}, status=403)
        reminder.assigned_to = assignee
    for field, value in data.items():
        if field != 'profile_id':
            setattr(reminder, field, value)
    reminder.save()
    record_activity(reminder.profile, request.user, 'Reminder updated', metadata={'reminder_id': reminder.pk})
    return Response(_payload(reminder))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_reminder_view(request, reminder_id):
    if response := denied(request, 'clientpulse.reminders.manage'):
        return response
    if not _queryset(request, 'clientpulse.reminders.manage').filter(pk=reminder_id).exists():
        return Response({'detail': 'Reminder not found.'}, status=404)
    try:
        reminder, next_reminder = complete_reminder(reminder_id, request.user)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response({'reminder': _payload(reminder), 'next_reminder_id': getattr(next_reminder, 'pk', None)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def snooze_reminder_view(request, reminder_id):
    if response := denied(request, 'clientpulse.reminders.manage'):
        return response
    if not _queryset(request, 'clientpulse.reminders.manage').filter(pk=reminder_id).exists():
        return Response({'detail': 'Reminder not found.'}, status=404)
    serializer = SnoozeInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    try:
        reminder = snooze_reminder(reminder_id, request.user, serializer.validated_data['snoozed_until'])
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response(_payload(reminder))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_reminder_view(request, reminder_id):
    if response := denied(request, 'clientpulse.reminders.manage'):
        return response
    reminder = _queryset(request, 'clientpulse.reminders.manage').filter(pk=reminder_id).first()
    if not reminder:
        return Response({'detail': 'Reminder not found.'}, status=404)
    if reminder.status == 'completed':
        return Response({'detail': 'Completed reminders cannot be cancelled.'}, status=400)
    reminder.status = 'cancelled'; reminder.save(update_fields=['status', 'updated_at'])
    record_activity(reminder.profile, request.user, 'Reminder cancelled', metadata={'reminder_id': reminder.pk})
    return Response(_payload(reminder))
