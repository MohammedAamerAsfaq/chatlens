"""Saved campaign recipient lists: who may be put on one, and copying a list into a campaign.

A list's members are re-checked every time the list is used, because a contact's account
can move company or become invisible to the user, and a group can stop being sendable
(the account left it, it became announcement-only, sending was turned off).
"""
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.tenancy.services.access import scope_queryset_to_visible_accounts

from ..models import CampaignAudience, CampaignList

# Same rules as the campaign group picker (GroupViewSet ?sendable=true) and
# views._sendable_campaign_group.
SENDABLE_GROUP_FILTER = {
    'can_send': True,
    'account_is_participant': True,
    'is_community': False,
    'is_community_announcement': False,
    'announce': False,
}


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


def eligible_for(campaign_list, user):
    if campaign_list.kind == CampaignAudience.GROUPS:
        return eligible_groups(user, campaign_list.company)
    return eligible_contacts(user, campaign_list.company)


def search_eligible(qs, kind, search):
    search = (search or '').strip()
    if not search:
        return qs
    if kind == CampaignAudience.GROUPS:
        return qs.filter(Q(name__icontains=search) | Q(wa_group_id__icontains=search))
    return qs.filter(
        Q(display_name__icontains=search)
        | Q(push_name__icontains=search)
        | Q(phone_number__icontains=search)
        | Q(wa_contact_id__icontains=search)
    )


def member_rows(campaign_list):
    return campaign_list.groups if campaign_list.kind == CampaignAudience.GROUPS else campaign_list.contacts


def member_field(campaign_list):
    return 'group_id' if campaign_list.kind == CampaignAudience.GROUPS else 'contact_id'


def campaign_list_for(campaign, list_id):
    """The company's saved list a campaign may use, matching the campaign's audience."""
    if not list_id:
        raise ValidationError({'list_id': 'Choose a saved list.'})
    try:
        campaign_list = CampaignList.objects.filter(pk=list_id, company=campaign.company).first()
    except (TypeError, ValueError):
        campaign_list = None
    if not campaign_list:
        raise ValidationError({'list_id': 'Saved list not found for this company.'})
    if campaign_list.kind != campaign.audience_type:
        wanted = 'group' if campaign.audience_type == CampaignAudience.GROUPS else 'contact'
        raise ValidationError({'list_id': f'This campaign sends to {wanted}s; choose a {wanted} list.'})
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
