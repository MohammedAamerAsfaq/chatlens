from dataclasses import dataclass
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.tenancy.models import Company, CompanyMembership

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
            membership = CompanyMembership.objects.create(
                company=company,
                user=user,
                role=CompanyMembership.ROLE_SUPER_USER,
                is_active=True,
            )
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
        role: str = CompanyMembership.ROLE_USER,
    ) -> EnrollmentResult:
        User = get_user_model()
        if not company:
            raise ValueError('company is required')
        if not company.is_active:
            raise ValueError('company must be active')
        if role not in {choice[0] for choice in CompanyMembership.ROLE_CHOICES}:
            raise ValueError('role is invalid')
        if not username.strip():
            raise ValueError('username is required')
        if not email.strip():
            raise ValueError('email is required')
        if not password:
            raise ValueError('password is required')
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
            membership = CompanyMembership.objects.create(
                company=company,
                user=user,
                role=role,
                is_active=True,
            )
            logger.info(
                'Company user created | company_id=%s user_id=%s membership_id=%s role=%s',
                company.pk, user.pk, membership.pk, role,
            )
            return EnrollmentResult(
                company_id=company.pk,
                user_id=user.pk,
                membership_id=membership.pk,
            )
        except Exception:
            logger.exception(
                'Company user creation failed | company_id=%s username=%s email=%s role=%s',
                company.pk if company else None, username, email, role,
            )
            raise
