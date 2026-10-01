from django.db import transaction
from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.models import (
    AuthorizationAuditEvent, CompanyMembership, CompanyRole, CompanyRolePermission,
    MembershipRoleAssignment, PermissionDefinition,
)
from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from apps.tenancy.services.authorization import bump_authorization_version, has_company_permission
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService


def _denied(request, code):
    return None if has_company_permission(request.user, code) else Response(
        {'detail': 'You do not have permission to perform this action.'},
        status=status.HTTP_403_FORBIDDEN,
    )


def _is_owner(membership):
    return membership.role_assignments.filter(role__is_owner_role=True, role__is_active=True).exists() or (
        not membership.role_assignments.exists() and membership.role == CompanyMembership.ROLE_SUPER_USER
    )


def _role_payload(role):
    return {
        'id': role.pk, 'key': role.key, 'name': role.name, 'description': role.description,
        'is_system_role': role.is_system_role, 'is_owner_role': role.is_owner_role,
        'is_active': role.is_active,
        'member_count': getattr(role, 'member_count', role.membership_assignments.filter(membership__is_active=True).count()),
        'permissions': [
            {'code': grant.permission.code, 'scope': grant.record_scope}
            for grant in role.permission_grants.select_related('permission').order_by('permission__code')
        ],
    }


def _membership_payload(membership):
    return {
        'id': membership.pk, 'is_active': membership.is_active,
        'authorization_version': membership.authorization_version,
        'user': {'id': membership.user_id, 'username': membership.user.username, 'email': membership.user.email},
        'roles': [
            {'id': item.role_id, 'key': item.role.key, 'name': item.role.name, 'is_owner_role': item.role.is_owner_role}
            for item in membership.role_assignments.select_related('role').filter(role__is_active=True).order_by('role__name')
        ],
    }


def _audit(company, actor, event_type, *, membership=None, role=None, before=None, after=None):
    AuthorizationAuditEvent.objects.create(
        company=company, actor=actor, event_type=event_type,
        target_membership=membership, target_role=role,
        before_snapshot=before or {}, after_snapshot=after or {},
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company_permissions_view(request):
    denied = _denied(request, 'users.roles.view')
    if denied:
        return denied
    rows = PermissionDefinition.objects.filter(is_active=True).order_by('area', 'code')
    return Response([{
        'code': row.code, 'area': row.area, 'label': row.label,
        'description': row.description, 'supports_scope': row.supports_scope,
        'is_sensitive': row.is_sensitive,
    } for row in rows])


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def company_roles_view(request):
    company = default_company_for_user(request.user)
    denied = _denied(request, 'users.roles.view' if request.method == 'GET' else 'users.roles.manage')
    if denied:
        return denied
    if request.method == 'POST':
        name = str(request.data.get('name') or '').strip()
        key = str(request.data.get('key') or '').strip().lower().replace(' ', '-')
        if not name or not key:
            return Response({'detail': 'name and key are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if CompanyRole.objects.filter(company=company, key=key).exists():
            return Response({'detail': 'A role with this key already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        role = CompanyRole.objects.create(
            company=company, key=key, name=name,
            description=str(request.data.get('description') or ''), created_by=request.user,
        )
        _audit(company, request.user, 'role.created', role=role, after=_role_payload(role))
        return Response(_role_payload(role), status=status.HTTP_201_CREATED)
    roles = CompanyRole.objects.filter(company=company).annotate(member_count=Count('membership_assignments'))
    return Response([_role_payload(role) for role in roles])


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def company_role_detail_view(request, role_id):
    company = default_company_for_user(request.user)
    denied = _denied(request, 'users.roles.manage')
    if denied:
        return denied
    role = CompanyRole.objects.select_for_update().filter(company=company, pk=role_id).first()
    if not role:
        return Response({'detail': 'Role not found.'}, status=status.HTTP_404_NOT_FOUND)
    if role.is_owner_role and not _is_owner(active_membership_for_user(request.user)):
        return Response({'detail': 'Only an Owner can modify the Owner role.'}, status=status.HTTP_403_FORBIDDEN)
    if role.is_owner_role and 'permissions' in request.data:
        return Response({'detail': 'Owner permissions are immutable.'}, status=status.HTTP_400_BAD_REQUEST)
    before = _role_payload(role)
    if not role.is_system_role:
        role.name = str(request.data.get('name', role.name)).strip() or role.name
        role.description = str(request.data.get('description', role.description))
        requested_active = request.data.get('is_active', role.is_active)
        role.is_active = requested_active in (True, 1, '1', 'true')
        role.updated_by = request.user
        role.save(update_fields=['name', 'description', 'is_active', 'updated_by', 'updated_at'])
    if 'permissions' in request.data:
        requested = request.data['permissions']
        if not isinstance(requested, list) or any(not isinstance(item, dict) for item in requested):
            return Response({'detail': 'permissions must be a list.'}, status=status.HTTP_400_BAD_REQUEST)
        codes = [item.get('code') for item in requested]
        if len(codes) != len(set(codes)):
            return Response({'detail': 'Permission codes cannot be duplicated.'}, status=status.HTTP_400_BAD_REQUEST)
        definitions = {row.code: row for row in PermissionDefinition.objects.filter(code__in=codes)}
        if len(definitions) != len(codes):
            return Response({'detail': 'One or more permission codes are invalid.'}, status=status.HTTP_400_BAD_REQUEST)
        if any(item.get('scope', 'all') not in {'own', 'assigned', 'all'} for item in requested):
            return Response({'detail': 'Permission scope is invalid.'}, status=status.HTTP_400_BAD_REQUEST)
        role.permission_grants.all().delete()
        CompanyRolePermission.objects.bulk_create([
            CompanyRolePermission(
                company=company, role=role, permission=definitions[item['code']],
                record_scope=item.get('scope', 'all') if definitions[item['code']].supports_scope else 'all',
                created_by=request.user,
            ) for item in requested
        ])
        for assignment in role.membership_assignments.select_related('membership'):
            bump_authorization_version(assignment.membership)
    _audit(company, request.user, 'role.updated', role=role, before=before, after=_role_payload(role))
    return Response(_role_payload(role))
