from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from apps.tenancy.models import Company, CompanyMembership
from apps.whatsapp_bridge.models import WhatsAppAccount


def available_companies_queryset(user) -> QuerySet:
    qs = Company.objects.all()
    if user.is_superuser:
        return qs
    return qs.filter(memberships__user=user, memberships__is_active=True).distinct()


def default_company_for_user(user):
    active_company = getattr(user, 'active_company', None)
    if active_company is not None:
        return active_company

    if user.is_superuser:
        control = Company.objects.filter(company_type=Company.TYPE_CONTROL, is_active=True).first()
        if control:
            return control

    memberships = (
        CompanyMembership.objects
        .filter(user=user, is_active=True, company__is_active=True)
        .select_related('company')
        .annotate(
            priority=Case(
                When(company__company_type=Company.TYPE_CONTROL, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by('priority', 'company__name')
    )
    membership = memberships.first()
    return membership.company if membership else None


def visible_companies_queryset(user) -> QuerySet:
    active_company = default_company_for_user(user)
    if active_company is None:
        return Company.objects.none()
    return Company.objects.filter(pk=active_company.pk)


def can_user_access_company(user, company_id) -> bool:
    if not company_id:
        return False
    return available_companies_queryset(user).filter(pk=company_id, is_active=True).exists()


def active_membership_for_user(user):
    company = default_company_for_user(user)
    if not company:
        return None
    return (
        CompanyMembership.objects
        .filter(user=user, company=company, is_active=True)
        .select_related('company')
        .first()
    )


def is_control_company_admin(user) -> bool:
    company = default_company_for_user(user)
    if not company or company.company_type != Company.TYPE_CONTROL:
        return False
    if user.is_superuser:
        return True
    membership = active_membership_for_user(user)
    if not membership:
        return False
    return membership.role in {CompanyMembership.ROLE_SUPER_USER, CompanyMembership.ROLE_ADMIN}


def company_for_whatsapp_account(account):
    if not account:
        return None
    if getattr(account, 'communication_account_id', None):
        communication_account = getattr(account, 'communication_account', None)
        if communication_account and communication_account.company_id:
            return communication_account.company
    owner = getattr(account, 'owner', None)
    return default_company_for_user(owner) if owner else None


def company_for_message(message):
    if not message:
        return None
    return company_for_whatsapp_account(getattr(message, 'account', None))


def visible_accounts_queryset(user, qs: QuerySet | None = None) -> QuerySet:
    qs = qs if qs is not None else WhatsAppAccount.objects.all()
    active_company = default_company_for_user(user)
    if active_company is not None:
        return qs.filter(communication_account__company=active_company).distinct()
    if user.is_superuser:
        return qs
    return qs.filter(
        Q(
            communication_account__company__memberships__user=user,
            communication_account__company__memberships__is_active=True,
        ) |
        Q(owner=user, communication_account__isnull=True)
    ).distinct()


def scope_queryset_to_visible_accounts(qs: QuerySet, user, account_field: str = 'account') -> QuerySet:
    if user.is_superuser:
        return qs
    visible_account_ids = visible_accounts_queryset(user).values('pk')
    return qs.filter(**{f'{account_field}__in': visible_account_ids}).distinct()


def scope_queryset_to_visible_companies(qs: QuerySet, user, company_field: str = 'company') -> QuerySet:
    if user.is_superuser:
        return qs
    visible_company_ids = visible_companies_queryset(user).values('pk')
    return qs.filter(**{f'{company_field}__in': visible_company_ids}).distinct()
