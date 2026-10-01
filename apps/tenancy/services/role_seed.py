from django.db import transaction

from apps.tenancy.models import (
    CompanyRole,
    CompanyRolePermission,
    MembershipRoleAssignment,
    PermissionDefinition,
)
from .permission_catalog import PERMISSION_SPECS, ROLE_GRANTS, ROLE_SPECS, default_scope


@transaction.atomic
def seed_permission_definitions():
    definitions = {}
    for spec in PERMISSION_SPECS:
        code = spec['code']
        defaults = {key: value for key, value in spec.items() if key != 'code'}
        definition, _ = PermissionDefinition.objects.update_or_create(code=code, defaults=defaults)
        definitions[code] = definition
    return definitions


@transaction.atomic
def seed_company_roles(company):
    definitions = seed_permission_definitions()
    roles = {}
    for key, spec in ROLE_SPECS.items():
        role, _ = CompanyRole.objects.update_or_create(
            company=company,
            key=key,
            defaults={
                'name': spec['name'],
                'description': spec['description'],
                'is_system_role': True,
                'is_owner_role': spec.get('owner', False),
                'is_active': True,
            },
        )
        roles[key] = role
        grants = [
            CompanyRolePermission(
                company=company,
                role=role,
                permission=definitions[code],
                record_scope=default_scope(key, next(item for item in PERMISSION_SPECS if item['code'] == code)),
            )
            for code in ROLE_GRANTS[key]
        ]
        CompanyRolePermission.objects.bulk_create(grants, ignore_conflicts=True)
    return roles


@transaction.atomic
def sync_legacy_membership_role(membership):
    roles = seed_company_roles(membership.company)
    MembershipRoleAssignment.objects.filter(
        membership=membership,
        source=MembershipRoleAssignment.SOURCE_LEGACY,
    ).exclude(role=roles[membership.role]).delete()
    assignment, _ = MembershipRoleAssignment.objects.get_or_create(
        company=membership.company,
        membership=membership,
        role=roles[membership.role],
        defaults={'source': MembershipRoleAssignment.SOURCE_LEGACY},
    )
    if assignment.source != MembershipRoleAssignment.SOURCE_LEGACY:
        assignment.source = MembershipRoleAssignment.SOURCE_LEGACY
        assignment.save(update_fields=['source'])
    return assignment
