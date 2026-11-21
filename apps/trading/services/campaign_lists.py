"""Saved campaign lists: what may be put on one, and copying a list into a campaign.

Contact and group lists hold recipients; product lists hold the products a formatted
campaign offers or asks for. A list's members are re-checked every time the list is
used, because a contact's account can move company or become invisible to the user, a
group can stop being sendable (the account left it, it became announcement-only, sending
was turned off) and a product can be deactivated.
"""
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.tenancy.services.access import scope_queryset_to_visible_accounts, visible_accounts_queryset

from ..models import CampaignList, CampaignListKind

# Same rules as the campaign group picker (GroupViewSet ?sendable=true) and
# views._sendable_campaign_group.
SENDABLE_GROUP_FILTER = {
    'can_send': True,
    'account_is_participant': True,
    'is_community': False,
    'is_community_announcement': False,
    'announce': False,
}

# Per kind: the membership relation on CampaignList, the member FK on that row, and
# whether members are scoped to WhatsApp accounts the user can see.
KIND_SPECS = {
    CampaignListKind.CONTACTS: {'rows': 'contacts', 'target': 'contact', 'account_scoped': True},
    CampaignListKind.GROUPS: {'rows': 'groups', 'target': 'group', 'account_scoped': True},
    CampaignListKind.PRODUCTS: {'rows': 'products', 'target': 'product', 'account_scoped': False},
}


def spec(campaign_list):
    return KIND_SPECS[campaign_list.kind]


def eligible_contacts(user, company):
    """Phone-number contacts on the company's accounts that the user can see. Linked IDs
    (@lid) are never campaign recipients."""
    from apps.whatsapp_bridge.models import WhatsAppContact

    qs = WhatsAppContact.objects.select_related('account').filter(
        account__communication_account__company=company,
        wa_contact_id__endswith='@s.whatsapp.net',
    )
    return scope_queryset_to_visible_accounts(qs, user, account_field='account')


def eligible_groups(user, company):
    from apps.whatsapp_bridge.models import WhatsAppGroup

    qs = WhatsAppGroup.objects.select_related('account').filter(
        account__communication_account__company=company, **SENDABLE_GROUP_FILTER,
    )
    return scope_queryset_to_visible_accounts(qs, user, account_field='account')


def eligible_products(user, company):
    """The company's active catalogue products (the same set the campaign product search offers)."""
    from ..models import Product

    return Product.objects.filter(company=company, is_active=True)


def eligible_for(campaign_list, user):
    if campaign_list.kind == CampaignListKind.GROUPS:
        return eligible_groups(user, campaign_list.company)
    if campaign_list.kind == CampaignListKind.PRODUCTS:
        return eligible_products(user, campaign_list.company)
    return eligible_contacts(user, campaign_list.company)


def search_eligible(qs, kind, search):
    search = (search or '').strip()
    if not search:
        return qs
    if kind == CampaignListKind.GROUPS:
        return qs.filter(Q(name__icontains=search) | Q(wa_group_id__icontains=search))
    if kind == CampaignListKind.PRODUCTS:
        return qs.filter(
            Q(name__icontains=search)
            | Q(brand__icontains=search)
            | Q(sku__icontains=search)
            | Q(alias_set__alias__icontains=search)
        ).distinct()
    return qs.filter(
        Q(display_name__icontains=search)
        | Q(push_name__icontains=search)
        | Q(phone_number__icontains=search)
        | Q(wa_contact_id__icontains=search)
    )


def member_rows(campaign_list):
    return getattr(campaign_list, spec(campaign_list)['rows'])


def member_field(campaign_list):
    return f"{spec(campaign_list)['target']}_id"


def visible_member_rows(campaign_list, user):
    """The list's rows the user may see and change: recipients on accounts the user can
    see; every product row (products are company-wide)."""
    rows = member_rows(campaign_list).all()
    if spec(campaign_list)['account_scoped']:
        rows = rows.filter(**{f"{spec(campaign_list)['target']}__account__in": visible_accounts_queryset(user).values('pk')})
    return rows


def _list_for(campaign, list_id, field):
    if not list_id:
        raise ValidationError({field: 'Choose a saved list.'})
    try:
        campaign_list = CampaignList.objects.filter(pk=list_id, company=campaign.company).first()
    except (TypeError, ValueError):
        campaign_list = None
    if not campaign_list:
        raise ValidationError({field: 'Saved list not found for this company.'})
    return campaign_list


def campaign_list_for(campaign, list_id, field='list_id'):
    """The company's saved recipient list a campaign may use, matching the campaign's audience."""
    campaign_list = _list_for(campaign, list_id, field)
    if campaign_list.kind != campaign.audience_type:
        wanted = 'group' if campaign.audience_type == CampaignListKind.GROUPS else 'contact'
        raise ValidationError({field: f'This campaign sends to {wanted}s; choose a {wanted} list.'})
    return campaign_list


def product_list_for(campaign, list_id, field='list_id'):
    """The company's saved product list; any campaign (contact or group, buying or selling) can use one."""
    campaign_list = _list_for(campaign, list_id, field)
    if campaign_list.kind != CampaignListKind.PRODUCTS:
        raise ValidationError({field: 'Choose a product list.'})
    return campaign_list


def usable_member_ids(campaign_list, user):
    """(ids the user can add to a campaign now, in list order; count of members that can't be)."""
    ids = list(member_rows(campaign_list).values_list(member_field(campaign_list), flat=True))
    usable = set(eligible_for(campaign_list, user).filter(pk__in=ids).values_list('pk', flat=True))
    return [pk for pk in ids if pk in usable], len(ids) - len(usable)


def add_campaign_groups(row_model, campaign_field, campaign, group_ids):
    """Bulk-add group recipients to a campaign; returns (added, already there)."""
    group_ids = list(group_ids)
    existing = set(row_model.objects.filter(**{campaign_field: campaign}).values_list('group_id', flat=True))
    new_ids = [pk for pk in group_ids if pk not in existing]
    row_model.objects.bulk_create(
        [row_model(**{campaign_field: campaign, 'group_id': pk}) for pk in new_ids],
        ignore_conflicts=True,
    )
    return len(new_ids), len(group_ids) - len(new_ids)


def add_campaign_products(campaign, product_ids, add_row):
    """Add products to a campaign through its own add_row(campaign, product) (which sets the
    row's quantity and price from the product); returns (added, already there)."""
    from ..models import Product

    product_ids = list(product_ids)
    existing = set(campaign.products.values_list('product_id', flat=True))
    new_ids = [pk for pk in product_ids if pk not in existing]
    products = Product.objects.in_bulk(new_ids)
    for pk in new_ids:
        add_row(campaign, products[pk])
    return len(new_ids), len(product_ids) - len(new_ids)


def apply_product_list(campaign, product_ids, add_row, replace):
    """Add a product list's products to a campaign, first removing every product it has when
    `replace`; returns (removed, added, already there). Call inside a transaction so a failed
    add leaves the campaign's products as they were."""
    removed = campaign.products.all().delete()[0] if replace else 0
    added, skipped = add_campaign_products(campaign, product_ids, add_row)
    return removed, added, skipped


def replace_flag(data, field='replace'):
    """The request's `replace` choice: absent means add; anything but a JSON boolean is refused."""
    value = data.get(field, False)
    if not isinstance(value, bool):
        raise ValidationError({field: 'Must be true or false.'})
    return value
