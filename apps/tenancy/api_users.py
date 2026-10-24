from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.api_views import _audit, _denied, _is_owner, _membership_payload
from apps.tenancy.models import (
    CommunicationAccount, CommunicationAccountAssignment, CompanyMembership,
    CompanyRole, MembershipRoleAssignment,
)
from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from apps.tenancy.services.authorization import bump_authorization_version, permission_scope_for_membership
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService


def _owner_count(company):
    return MembershipRoleAssignment.objects.filter(
        company=company, role__is_owner_role=True, membership__is_active=True,
    ).values('membership_id').distinct().count()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def company_users_view(request):
    company = default_company_for_user(request.user)
    denied = _denied(request, 'users.memberships.view' if request.method == 'GET' else 'users.memberships.manage')
    if denied:
        return denied
    if request.method == 'POST':
        roles = {role.key: role for role in CompanyRole.objects.filter(company=company, is_active=True)}
        if 'user' not in roles:
            return Response({'detail': 'Default company roles are not initialized.'}, status=status.HTTP_409_CONFLICT)
        try:
            result = CompanyEnrollmentService().create_company_user(
                company=company,
                email=str(request.data.get('email') or '').strip(),
                username=str(request.data.get('username') or '').strip(),
                password=request.data.get('password') or '',
                role=CompanyMembership.ROLE_USER,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        membership = CompanyMembership.objects.select_related('user').get(pk=result.membership_id)
        role_ids = request.data.get('role_ids') or [roles['user'].pk]
        error = _replace_roles(request, membership, role_ids)
        if error:
            return error
        _audit(company, request.user, 'membership.created', membership=membership, after=_membership_payload(membership))
        return Response(_membership_payload(membership), status=status.HTTP_201_CREATED)
    memberships = CompanyMembership.objects.filter(company=company).select_related('user').order_by('user__username')
    return Response([_membership_payload(item) for item in memberships])


@transaction.atomic
def _replace_roles(request, membership, role_ids):
    if not isinstance(role_ids, list) or not role_ids:
        return Response({'detail': 'At least one role is required.'}, status=status.HTTP_400_BAD_REQUEST)
    roles = list(CompanyRole.objects.filter(company=membership.company, is_active=True, pk__in=role_ids))
    if len(roles) != len(set(role_ids)):
        return Response({'detail': 'One or more roles were not found.'}, status=status.HTTP_400_BAD_REQUEST)
    actor_membership = active_membership_for_user(request.user)
    changes_owner = any(role.is_owner_role for role in roles) or _is_owner(membership)
    if changes_owner and not _is_owner(actor_membership):
        return Response({'detail': 'Only an Owner can assign or remove the Owner role.'}, status=status.HTTP_403_FORBIDDEN)
    removing_owner = _is_owner(membership) and not any(role.is_owner_role for role in roles)
    if removing_owner and membership.is_active and _owner_count(membership.company) <= 1:
        return Response({'detail': 'A company must retain an active Owner.'}, status=status.HTTP_400_BAD_REQUEST)
    membership.role_assignments.all().delete()
    MembershipRoleAssignment.objects.bulk_create([
        MembershipRoleAssignment(
            company=membership.company, membership=membership, role=role,
            source=MembershipRoleAssignment.SOURCE_MANUAL, assigned_by=request.user,
        ) for role in roles
    ])
    precedence = ['super_user', 'admin', 'manager', 'user', 'viewer']
    keys = {role.key for role in roles}
    membership.role = next((key for key in precedence if key in keys), CompanyMembership.ROLE_VIEWER)
    membership.save(update_fields=['role'])
    bump_authorization_version(membership)
    return None


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def company_user_detail_view(request, membership_id):
    company = default_company_for_user(request.user)
    denied = _denied(request, 'users.memberships.manage')
    if denied:
        return denied
    membership = CompanyMembership.objects.select_for_update().select_related('user').filter(
        company=company, pk=membership_id,
    ).first()
    if not membership:
        return Response({'detail': 'Membership not found.'}, status=status.HTTP_404_NOT_FOUND)
    before = _membership_payload(membership)
    if 'role_ids' in request.data:
        error = _replace_roles(request, membership, request.data['role_ids'])
        if error:
            return error
    if 'is_active' in request.data:
        active = request.data['is_active'] in (True, 1, '1', 'true')
        if not active and membership.is_active and _is_owner(membership) and _owner_count(company) <= 1:
            return Response({'detail': 'A company must retain an active Owner.'}, status=status.HTTP_400_BAD_REQUEST)
        membership.is_active = active
        membership.save(update_fields=['is_active'])
        bump_authorization_version(membership)
    _audit(company, request.user, 'membership.updated', membership=membership, before=before, after=_membership_payload(membership))
    return Response(_membership_payload(membership))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company_communication_accounts_view(request):
    company = default_company_for_user(request.user)
    denied = _denied(request, 'users.memberships.view')
    if denied:
        return denied
    accounts = CommunicationAccount.objects.filter(company=company).select_related(
        'provider', 'whatsapp_account', 'whatsapp_account__owner',
    ).order_by('name', 'id')
    rows = []
    for account in accounts:
        whatsapp = getattr(account, 'whatsapp_account', None)
        rows.append({
            'id': account.pk,
            'name': account.name,
            'channel': account.channel,
            'is_active': account.is_active,
            'provider': account.provider.name,
            'whatsapp_account_id': whatsapp.pk if whatsapp else None,
            'display_name': whatsapp.display_name if whatsapp else '',
            'phone_number': whatsapp.phone_number if whatsapp else '',
            'owner_user_id': whatsapp.owner_id if whatsapp else None,
        })
    return Response(rows)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def company_user_communication_accounts_view(request, membership_id):
    company = default_company_for_user(request.user)
    denied = _denied(request, 'users.memberships.manage')
    if denied:
        return denied
    membership = CompanyMembership.objects.select_for_update().select_related('user').filter(
        company=company, pk=membership_id,
    ).first()
    if not membership:
        return Response({'detail': 'Membership not found.'}, status=status.HTTP_404_NOT_FOUND)

    requested_ids = request.data.get('communication_account_ids')
    if not isinstance(requested_ids, list):
        return Response(
            {'detail': 'communication_account_ids must be a list.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        requested_ids = {int(value) for value in requested_ids}
    except (TypeError, ValueError):
        return Response({'detail': 'Account IDs must be integers.'}, status=status.HTTP_400_BAD_REQUEST)

    company_ids = set(CommunicationAccount.objects.filter(
        company=company, pk__in=requested_ids,
    ).values_list('pk', flat=True))
    if company_ids != requested_ids:
        return Response({'detail': 'One or more accounts were not found.'}, status=status.HTTP_400_BAD_REQUEST)

    owner_ids = set(CommunicationAccount.objects.filter(
        company=company, whatsapp_account__owner_id=membership.user_id,
    ).values_list('pk', flat=True))
    selected_ids = requested_ids | owner_ids
    before = _membership_payload(membership)
    CommunicationAccountAssignment.objects.filter(
        company=company, membership=membership,
    ).exclude(communication_account_id__in=selected_ids).update(is_active=False)

    for account_id in selected_ids:
        access_level = (
            CommunicationAccountAssignment.ACCESS_OWNER
            if account_id in owner_ids else CommunicationAccountAssignment.ACCESS_MEMBER
        )
        CommunicationAccountAssignment.objects.update_or_create(
            company=company,
            membership=membership,
            communication_account_id=account_id,
            defaults={
                'access_level': access_level,
                'is_active': True,
                'assigned_by': request.user,
            },
        )
    bump_authorization_version(membership)
    after = _membership_payload(membership)
    _audit(
        company, request.user, 'membership.communication_accounts.updated',
        membership=membership, before=before, after=after,
    )
    after['account_access_scope'] = permission_scope_for_membership(
        membership, 'conversations.accounts.view',
    )
    return Response(after)
