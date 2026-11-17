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
    """Create any built-in role the company is missing, with its default permissions.

    A role that already exists is left exactly as the company has edited it: its name,
    permissions and active flag are the company's to change on the Roles page.
    """
    definitions = seed_permission_definitions()
    specs = {item['code']: item for item in PERMISSION_SPECS}
    roles = {}
    for key, spec in ROLE_SPECS.items():
        role, created = CompanyRole.objects.get_or_create(
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
        if created:
            codes = set(ROLE_GRANTS[key])
        elif role.is_owner_role:
            # The Owner holds every permission, including ones added to the catalog later.
            codes = set(ROLE_GRANTS[key]) - set(role.permission_grants.values_list('permission__code', flat=True))
        else:
            codes = set()
        CompanyRolePermission.objects.bulk_create([
            CompanyRolePermission(
                company=company, role=role, permission=definitions[code],
                record_scope=default_scope(key, specs[code]),
            )
            for code in sorted(codes)
        ])
    return roles


@transaction.atomic
def assign_role(membership, role_key, *, assigned_by=None, replace=False):
    """Give a membership one of its company's roles, chosen by key.

    With replace=True every other role the membership holds is taken away. Raises
    ValueError when the company has no active role with that key.
    """
    roles = CompanyRole.objects.filter(company=membership.company, key=role_key)
    if not roles.exists():
        seed_company_roles(membership.company)
    role = roles.filter(is_active=True).first()
    if role is None:
        raise ValueError(f'This company has no active role {role_key!r}.')
    if replace:
        membership.role_assignments.exclude(role=role).delete()
    assignment, _ = MembershipRoleAssignment.objects.get_or_create(
        company=membership.company,
        membership=membership,
        role=role,
        defaults={'source': MembershipRoleAssignment.SOURCE_MANUAL, 'assigned_by': assigned_by},
    )
    return assignment
