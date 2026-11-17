from dataclasses import dataclass
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.tenancy.models import Company, CompanyMembership
from apps.tenancy.services.company_bootstrap import seed_required_company_settings
from apps.tenancy.services.permission_catalog import OWNER_ROLE_KEY
from apps.tenancy.services.role_seed import assign_role, seed_company_roles
from apps.tenancy.services.user_admin import check_password_strength

logger = logging.getLogger(__name__)


@dataclass
class EnrollmentResult:
    company_id: int
    user_id: int
    membership_id: int


class CompanyEnrollmentService:
    @transaction.atomic
    def enroll_company(
        self,
        *,
        company_name: str,
        email: str,
        username: str,
        password: str,
        industry_type: str = Company.INDUSTRY_GENERAL,
    ) -> EnrollmentResult:
        User = get_user_model()
        slug = slugify(company_name).strip()
        if not company_name.strip():
            raise ValueError('company_name is required')
        if not slug:
            raise ValueError('company_name must produce a valid slug')
        if not username.strip():
            raise ValueError('username is required')
        if not email.strip():
            raise ValueError('email is required')
        if not password:
            raise ValueError('password is required')
        check_password_strength(password, username=username, email=email)
        if Company.objects.filter(slug=slug).exists():
            raise ValueError(f'Company with slug {slug!r} already exists')
        if User.objects.filter(username=username).exists():
            raise ValueError(f'Username {username!r} already exists')
        if User.objects.filter(email=email).exists():
            raise ValueError(f'Email {email!r} already exists')

        try:
            company = Company.objects.create(
                name=company_name.strip(),
                slug=slug,
                company_type=Company.TYPE_CUSTOMER,
                industry_type=industry_type,
            )
            user = User.objects.create_user(
                username=username.strip(),
                email=email.strip(),
                password=password,
            )
            membership = CompanyMembership.objects.create(company=company, user=user, is_active=True)
            seed_required_company_settings(company)
            from apps.clientpulse.models import ClientPulseSettings
            ClientPulseSettings.objects.get_or_create(company=company)
            if company.industry_type == Company.INDUSTRY_REAL_ESTATE:
                from apps.real_estate.models import RealEstateSettings
                from apps.real_estate.services.property_types import seed_default_property_types
                RealEstateSettings.objects.get_or_create(company=company)
                seed_default_property_types(company)
            from apps.clientpulse.services.scheduling import ensure_company_reminder_schedule
            ensure_company_reminder_schedule(company)
            seed_company_roles(company)
            assign_role(membership, OWNER_ROLE_KEY)
            logger.info(
                'Company enrolled | company_id=%s user_id=%s membership_id=%s',
                company.pk, user.pk, membership.pk,
            )
            return EnrollmentResult(
                company_id=company.pk,
                user_id=user.pk,
                membership_id=membership.pk,
            )
        except Exception:
            logger.exception(
                'Company enrollment failed | company_name=%s username=%s email=%s',
                company_name, username, email,
            )
            raise

    @transaction.atomic
    def create_company_user(
        self,
        *,
        company: Company,
        email: str,
        username: str,
        password: str,
        role_key: str,
        assigned_by=None,
    ) -> EnrollmentResult:
        """Create a login and a membership holding the company's role with this key."""
        User = get_user_model()
        if not company:
            raise ValueError('company is required')
        if not company.is_active:
            raise ValueError('company must be active')
        if not username.strip():
            raise ValueError('username is required')
        if not email.strip():
            raise ValueError('email is required')
        if not password:
            raise ValueError('password is required')
        check_password_strength(password, username=username, email=email)
        if User.objects.filter(username=username).exists():
            raise ValueError(f'Username {username!r} already exists')
        if User.objects.filter(email=email).exists():
            raise ValueError(f'Email {email!r} already exists')

        try:
            user = User.objects.create_user(
                username=username.strip(),
                email=email.strip(),
                password=password,
            )
            membership = CompanyMembership.objects.create(company=company, user=user, is_active=True)
            assign_role(membership, role_key, assigned_by=assigned_by)
            logger.info(
                'Company user created | company_id=%s user_id=%s membership_id=%s role_key=%s',
                company.pk, user.pk, membership.pk, role_key,
            )
            return EnrollmentResult(
                company_id=company.pk,
                user_id=user.pk,
                membership_id=membership.pk,
            )
        except Exception:
            logger.exception(
                'Company user creation failed | company_id=%s username=%s email=%s role_key=%s',
                company.pk if company else None, username, email, role_key,
            )
            raise
