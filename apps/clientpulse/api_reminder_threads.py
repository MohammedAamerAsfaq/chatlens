from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied
from apps.clientpulse.api_reminders import _payload, _queryset


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reminder_thread_view(request, reminder_id):
    if response := denied(request, 'clientpulse.reminders.view'):
        return response
    reminders = _queryset(request, 'clientpulse.reminders.view')
    reminder = reminders.filter(pk=reminder_id).first()
    if not reminder:
        return Response({'detail': 'Reminder not found.'}, status=404)
    thread = reminders.filter(thread_key=reminder.thread_key).order_by('created_at', 'pk')
    return Response({
        'thread_key': str(reminder.thread_key),
        'profile': _payload(reminder)['profile'],
        'results': [_payload(item) for item in thread],
    })
