from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none
from apps.clientpulse.serializers import IdentityInputSerializer
from apps.clientpulse.services.profile_service import record_activity
from apps.tenancy.models import CompanyContactIdentity


def _payload(identity):
    return {
        'id': identity.pk, 'identity_type': identity.identity_type,
        'value': identity.value, 'label': identity.label,
        'is_primary': identity.is_primary, 'is_verified': identity.is_verified,
        'source_type': identity.source_type,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def client_identities_view(request, profile_id):
    if response := denied(request, 'clientpulse.clients.update'):
        return response
    profile = profile_or_none(request, profile_id, 'clientpulse.clients.update')
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    serializer = IdentityInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    identity = CompanyContactIdentity.objects.create(
        contact=profile.contact,
        source_type=CompanyContactIdentity.SOURCE_MANUAL,
        **serializer.validated_data,
    )
    record_activity(profile, request.user, 'Contact identity added', metadata={
        'identity_id': identity.pk, 'identity_type': identity.identity_type,
    })
    return Response(_payload(identity), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def client_identity_detail_view(request, profile_id, identity_id):
    if response := denied(request, 'clientpulse.clients.update'):
        return response
    profile = profile_or_none(request, profile_id, 'clientpulse.clients.update')
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    identity = profile.contact.identities.filter(pk=identity_id, is_active=True).first()
    if not identity:
        return Response({'detail': 'Identity not found.'}, status=404)
    if request.method == 'DELETE':
        identity.is_active = False
        identity.save(update_fields=['is_active'])
        record_activity(profile, request.user, 'Contact identity removed', metadata={
            'identity_id': identity.pk, 'identity_type': identity.identity_type,
        })
        return Response(status=204)
    serializer = IdentityInputSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    for field, value in serializer.validated_data.items():
        setattr(identity, field, value)
    identity.save()
    record_activity(profile, request.user, 'Contact identity updated', metadata={
        'identity_id': identity.pk, 'identity_type': identity.identity_type,
    })
    return Response(_payload(identity))
