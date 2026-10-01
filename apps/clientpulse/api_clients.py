from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none, scoped_profiles
from apps.clientpulse.api_payloads import profile_payload
from apps.clientpulse.models import ClientProfile, ClientPulseSettings, ClientTag
from apps.clientpulse.serializers import ClientProfileInputSerializer
from apps.clientpulse.services.profile_service import create_profile, record_activity, update_profile
from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import default_company_for_user


CONTACT_FIELDS = {
    'contact_type', 'first_name', 'middle_name', 'last_name',
    'display_name', 'legal_name', 'category', 'notes',
}
PROFILE_FIELDS = {
    'lifecycle_stage', 'status', 'priority', 'source', 'preferred_channel',
    'preferred_language', 'timezone', 'last_contacted_at', 'last_inbound_at',
    'next_follow_up_at', 'do_not_contact', 'do_not_contact_reason',
}


class ClientPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def _related(queryset):
    return queryset.select_related('contact', 'owner__user').prefetch_related('tag_assignments__tag')


def _validate_relations(company, data):
    owner = None
    if 'owner_id' in data and data['owner_id'] is not None:
        owner = CompanyMembership.objects.filter(
            company=company, pk=data['owner_id'], is_active=True,
        ).first()
        if not owner:
            return None, None, Response({'owner_id': ['Invalid company member.']}, status=400)
    tag_ids = list(dict.fromkeys(data.get('tag_ids', [])))
    if tag_ids and ClientTag.objects.filter(company=company, is_active=True, pk__in=tag_ids).count() != len(tag_ids):
        return None, None, Response({'tag_ids': ['One or more tags are invalid.']}, status=400)
    return owner, tag_ids, None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def clients_view(request):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.clients.create'
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    if request.method == 'POST':
        serializer = ClientProfileInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        data = serializer.validated_data
        owner, tag_ids, error = _validate_relations(company, data)
        if error:
            return error
        contact_data = {key: data[key] for key in CONTACT_FIELDS if key in data}
        profile_data = {key: data[key] for key in PROFILE_FIELDS if key in data}
        settings, _ = ClientPulseSettings.objects.get_or_create(company=company)
        profile_data.setdefault('timezone', settings.default_timezone)
        profile_data.setdefault('preferred_language', settings.default_language)
        if 'owner_id' in data:
            profile_data['owner'] = owner
        profile = create_profile(
            company, request.user, contact_data, profile_data,
            data.get('identities', []), tag_ids,
        )
        return Response(profile_payload(_related(ClientProfile.objects).get(pk=profile.pk), detail=True), status=201)

    queryset = _related(scoped_profiles(request))
    requested_status = request.query_params.get('status', 'active')
    if requested_status != 'all':
        queryset = queryset.filter(status=requested_status)
    search = request.query_params.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(contact__display_name__icontains=search) | Q(contact__legal_name__icontains=search)
            | Q(contact__identities__value__icontains=search)
        ).distinct()
    for key in ('lifecycle_stage', 'priority', 'source'):
        if value := request.query_params.get(key):
            queryset = queryset.filter(**{key: value})
    if owner_id := request.query_params.get('owner_id'):
        queryset = queryset.filter(owner_id=owner_id)
    if tag_id := request.query_params.get('tag_id'):
        queryset = queryset.filter(tag_assignments__tag_id=tag_id)
    ordering = request.query_params.get('ordering', '-updated_at')
    allowed = {'updated_at', '-updated_at', 'contact__display_name', '-contact__display_name',
               'next_follow_up_at', '-next_follow_up_at'}
    queryset = queryset.order_by(ordering if ordering in allowed else '-updated_at')
    paginator = ClientPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([profile_payload(item) for item in page])


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def client_detail_view(request, profile_id):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.clients.update'
    if response := denied(request, permission):
        return response
    profile = profile_or_none(request, profile_id, permission)
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    if request.method == 'PATCH':
        serializer = ClientProfileInputSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        data = serializer.validated_data
        owner, tag_ids, error = _validate_relations(profile.company, data)
        if error:
            return error
        contact_data = {key: data[key] for key in CONTACT_FIELDS if key in data}
        profile_data = {key: data[key] for key in PROFILE_FIELDS if key in data}
        if 'owner_id' in data:
            profile_data['owner'] = owner
        update_profile(profile, request.user, contact_data, profile_data, tag_ids if 'tag_ids' in data else None)
    profile = _related(ClientProfile.objects).get(pk=profile.pk)
    return Response(profile_payload(profile, detail=True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_client_view(request, profile_id):
    if response := denied(request, 'clientpulse.clients.archive'):
        return response
    profile = profile_or_none(request, profile_id, 'clientpulse.clients.archive')
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    profile.status = 'archived'; profile.updated_by = request.user
    profile.contact.is_active = False; profile.contact.archived_at = timezone.now()
    profile.contact.updated_by = request.user; profile.contact.save()
    profile.save()
    record_activity(profile, request.user, 'Client archived')
    return Response({'status': 'archived'})
