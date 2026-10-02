from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none
from apps.clientpulse.serializers import ManualFollowUpSerializer
from apps.clientpulse.services.manual_follow_up import queue_manual_follow_up


ERROR_MESSAGES = {
    'client_not_active': 'Follow-up is blocked because this client is not active.',
    'client_do_not_contact': 'Follow-up is blocked by the client do-not-contact setting.',
    'whatsapp_contact_not_linked': 'Select a WhatsApp contact linked to this client.',
    'whatsapp_destination_invalid': 'The linked WhatsApp contact has no valid destination.',
    'outbound_asset_not_found': 'The selected image was not found for this company.',
    'follow_up_consent_unknown': 'Granted WhatsApp follow-up consent is required.',
    'follow_up_consent_denied': 'WhatsApp follow-up consent was denied.',
    'follow_up_consent_revoked': 'WhatsApp follow-up consent was revoked.',
}


def _payload(outbound, created, consent):
    return {
        'id': outbound.pk, 'created': created, 'status': outbound.status,
        'status_reason': outbound.status_reason,
        'correlation_id': outbound.correlation_id,
        'new_chat_state': outbound.new_chat_state,
        'content_type': outbound.content_type,
        'consent': consent,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_follow_up_view(request, profile_id):
    permission = 'clientpulse.messages.send_manual'
    if response := denied(request, permission):
        return response
    profile = profile_or_none(request, profile_id, permission)
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    serializer = ManualFollowUpSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = serializer.validated_data
    try:
        outbound, created, consent = queue_manual_follow_up(
            profile=profile, actor=request.user,
            contact_id=data['whatsapp_contact_id'], text=data.get('text', ''),
            asset_id=data.get('asset_id'), idempotency_key=data['idempotency_key'],
            confirm_new_chat=data.get('confirm_new_chat', False),
        )
    except ValueError as exc:
        code = str(exc)
        if code == 'likely_new_chat_confirmation_required':
            return Response({
                'detail': 'This may start a new chat. Explicit confirmation is required.',
                'code': code,
            }, status=409)
        return Response({'detail': ERROR_MESSAGES.get(code, code), 'code': code}, status=400)
    return Response(_payload(outbound, created, consent), status=201 if created else 200)
