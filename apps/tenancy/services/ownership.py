"""Who owns a company: members holding its active Owner role."""

from apps.tenancy.models import MembershipRoleAssignment


def is_owner(membership):
    if membership is None:
        return False
    return membership.role_assignments.filter(role__is_owner_role=True, role__is_active=True).exists()


def owner_memberships(company):
    """Active memberships of the company that hold its active Owner role."""
    return company.memberships.filter(
        is_active=True,
        role_assignments__role__is_owner_role=True,
        role_assignments__role__is_active=True,
    ).distinct()


def active_owner_count(company):
    return MembershipRoleAssignment.objects.filter(
        company=company, role__is_owner_role=True, role__is_active=True, membership__is_active=True,
    ).values('membership_id').distinct().count()
