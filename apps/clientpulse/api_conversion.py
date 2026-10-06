from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none
from apps.clientpulse.api_payloads import profile_payload
from apps.clientpulse.models import ClientProfile
from apps.clientpulse.services.conversation_conversion import (
    ConversationConversionError, convert_conversation_contact, find_conversion_target,
)
from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from apps.whatsapp_bridge.models import WhatsAppContact


class ConversationConversionSerializer(serializers.Serializer):
    lifecycle_stage = serializers.ChoiceField(choices=(
        'lead', 'prospect', 'active_customer',
    ))


class ConversationContactPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def _contact_payload(contact):
    profile = getattr(getattr(contact, 'company_contact', None), 'client_profile', None)
    communication = contact.account.communication_account
    return {
        'id': contact.pk,
        'display_name': contact.display_name or contact.push_name or contact.phone_number,
        'phone_number': contact.phone_number,
        'account_name': (
            contact.account.display_name or communication.name
            or contact.account.phone_number or f'Account {contact.account_id}'
        ),
        'profile_id': profile.pk if profile else None,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_contact_candidates_view(request):
    if response := denied(request, 'clientpulse.clients.view'):
        return response
    company = default_company_for_user(request.user)
    if not company:
        return Response({'detail': 'No active company is selected.'}, status=status.HTTP_404_NOT_FOUND)
    queryset = WhatsAppContact.objects.select_related(
        'account__communication_account', 'company_contact__client_profile',
    ).filter(
        account__communication_account__company=company,
    ).exclude(
        Q(wa_contact_id__endswith='@g.us') | Q(wa_contact_id__endswith='@newsletter')
        | Q(wa_contact_id__endswith='@broadcast'),
    ).order_by('display_name', 'push_name', 'phone_number', 'pk')
    membership = active_membership_for_user(request.user)
    is_company_admin = request.user.is_superuser or (
        membership and membership.role in {
            CompanyMembership.ROLE_SUPER_USER, CompanyMembership.ROLE_ADMIN,
        }
    )
    if not is_company_admin:
        queryset = queryset.filter(account__owner=request.user)
    search = request.query_params.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(display_name__icontains=search) | Q(push_name__icontains=search)
            | Q(phone_number__icontains=search) | Q(wa_contact_id__icontains=search),
        )
    paginator = ConversationContactPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([_contact_payload(contact) for contact in page])


def _profile(profile_id):
    return ClientProfile.objects.select_related('contact', 'owner__user').prefetch_related(
        'tag_assignments__tag', 'contact__identities', 'contact__whatsapp_contacts__account',
    ).get(pk=profile_id)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def convert_conversation_contact_view(request, whatsapp_contact_id):
    company = default_company_for_user(request.user)
    if not company:
        return Response({'detail': 'No active company is selected.'}, status=status.HTTP_404_NOT_FOUND)
    whatsapp_contact = WhatsAppContact.objects.select_related(
        'account__communication_account', 'company_contact__client_profile',
    ).filter(
        pk=whatsapp_contact_id,
        account__communication_account__company=company,
    ).first()
    if not whatsapp_contact:
        return Response({'detail': 'WhatsApp contact not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ConversationConversionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        target = find_conversion_target(whatsapp_contact, company)
    except ConversationConversionError as exc:
        return Response({'code': exc.code, 'detail': exc.detail}, status=status.HTTP_409_CONFLICT)

    permission = 'clientpulse.clients.update' if target.profile else 'clientpulse.clients.create'
    if response := denied(request, permission):
        return response
    if target.profile and not profile_or_none(request, target.profile.pk, permission):
        return Response({'detail': 'Client not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        profile, created, changed = convert_conversation_contact(
            whatsapp_contact, company, request.user,
            serializer.validated_data['lifecycle_stage'],
            expected_profile_id=target.profile.pk if target.profile else None,
        )
    except ConversationConversionError as exc:
        return Response({'code': exc.code, 'detail': exc.detail}, status=status.HTTP_409_CONFLICT)

    return Response({
        'created': created,
        'changed': changed,
        'profile': profile_payload(_profile(profile.pk), detail=True),
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
