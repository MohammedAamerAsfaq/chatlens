"""Helpers for tests that need company members."""

from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.role_seed import assign_role


def create_member(*, company, user, role='user', **fields):
    """A membership holding the company's built-in role with this key (seeded if missing)."""
    membership = CompanyMembership.objects.create(company=company, user=user, **fields)
    assign_role(membership, role)
    return membership
