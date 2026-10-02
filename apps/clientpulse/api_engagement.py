from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none
from apps.clientpulse.api_payloads import activity_payload, note_payload
from apps.clientpulse.models import ClientNote, ContactConsent
from apps.clientpulse.serializers import ClientNoteInputSerializer, ConsentInputSerializer
from apps.clientpulse.services.profile_service import record_activity


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_timeline_view(request, profile_id):
    if response := denied(request, 'clientpulse.clients.view'):
        return response
    profile = profile_or_none(request, profile_id)
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    rows = list(profile.activities.select_related('created_by')[:100])
    outbound_ids = [
        int(row.source_id) for row in rows
        if row.source_model == 'outbound_message' and row.source_id.isdigit()
    ]
    from apps.whatsapp_bridge.models import OutboundMessage
    outbound = {
        item.pk: item for item in OutboundMessage.objects.select_related('whatsapp_account').filter(
            company=profile.company, pk__in=outbound_ids,
        )
    }
    return Response([
        activity_payload(row, outbound.get(int(row.source_id)) if row.source_id.isdigit() else None)
        for row in rows
    ])


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_notes_view(request, profile_id):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.notes.manage'
    if response := denied(request, permission):
        return response
    profile = profile_or_none(request, profile_id, permission)
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    if request.method == 'GET':
        return Response([note_payload(note) for note in profile.notes.select_related('created_by')])
    serializer = ClientNoteInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    note = ClientNote.objects.create(
        company=profile.company, profile=profile,
        created_by=request.user, updated_by=request.user, **serializer.validated_data,
    )
    record_activity(
        profile, request.user, 'Note added', summary=note.body[:300],
        activity_type='note', metadata={'note_id': note.pk},
    )
    return Response(note_payload(note), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def client_note_detail_view(request, note_id):
    if response := denied(request, 'clientpulse.notes.manage'):
        return response
    note = ClientNote.objects.select_related('profile').filter(pk=note_id).first()
    if not note or not profile_or_none(request, note.profile_id, 'clientpulse.notes.manage'):
        return Response({'detail': 'Note not found.'}, status=404)
    if request.method == 'DELETE':
        profile = note.profile
        record_activity(
            profile, request.user, 'Note deleted', summary=note.body[:300],
            metadata={'note_id': note.pk},
        )
        note.delete()
        return Response(status=204)
    serializer = ClientNoteInputSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    before = {'body': note.body, 'is_pinned': note.is_pinned}
    for field, value in serializer.validated_data.items():
        setattr(note, field, value)
    note.updated_by = request.user
    note.save()
    record_activity(note.profile, request.user, 'Note updated', metadata={
        'note_id': note.pk, 'before': before,
        'after': {'body': note.body, 'is_pinned': note.is_pinned},
    })
    return Response(note_payload(note))


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def client_consents_view(request, profile_id):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.consent.manage'
    if response := denied(request, permission):
        return response
    profile = profile_or_none(request, profile_id, permission)
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    if request.method == 'PUT':
        serializer = ConsentInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        data = serializer.validated_data
        now = timezone.now()
        consent, _ = ContactConsent.objects.update_or_create(
            company=profile.company, profile=profile,
            channel=data['channel'], purpose=data['purpose'],
            defaults={
                'status': data['status'], 'source': data.get('source', ''),
                'evidence': data.get('evidence', {}),
                'captured_at': now if data['status'] == 'granted' else None,
                'revoked_at': now if data['status'] == 'revoked' else None,
            },
        )
        record_activity(profile, request.user, 'Consent updated', metadata={
            'consent_id': consent.pk, 'channel': consent.channel,
            'purpose': consent.purpose, 'status': consent.status,
        })
    return Response([{
        'id': item.pk, 'channel': item.channel, 'purpose': item.purpose,
        'status': item.status, 'source': item.source,
        'captured_at': item.captured_at, 'revoked_at': item.revoked_at,
    } for item in profile.consents.all()])
