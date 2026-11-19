from django.db import models
from django.db.models.functions import Lower

from .campaign_audience import CampaignAudience


class CampaignList(models.Model):
    """A saved, reusable set of campaign recipients: customers (kind contacts) or
    WhatsApp groups (kind groups). Lists belong to a company; applying one to a
    campaign copies its members into the campaign's recipients."""

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='campaign_lists')
    kind = models.CharField(max_length=20, choices=CampaignAudience.choices, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='campaign_lists_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_campaign_list'
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(
                'company', 'kind', Lower('name'), name='unique_campaign_list_name',
                violation_error_message='A list with this name already exists.',
            ),
        ]

    def __str__(self):
        return self.name


class CampaignListContact(models.Model):
    campaign_list = models.ForeignKey(CampaignList, on_delete=models.CASCADE, related_name='contacts')
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact', on_delete=models.CASCADE, related_name='campaign_list_rows',
    )
    added_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_campaign_list_contact'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['campaign_list', 'contact'], name='unique_campaign_list_contact'),
        ]


class CampaignListGroup(models.Model):
    campaign_list = models.ForeignKey(CampaignList, on_delete=models.CASCADE, related_name='groups')
    group = models.ForeignKey(
        'whatsapp_bridge.WhatsAppGroup', on_delete=models.CASCADE, related_name='campaign_list_rows',
    )
    added_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_campaign_list_group'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['campaign_list', 'group'], name='unique_campaign_list_group'),
        ]
