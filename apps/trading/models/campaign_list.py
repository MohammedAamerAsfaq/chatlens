from django.db import models
from django.db.models.functions import Lower


class CampaignListKind(models.TextChoices):
    # contacts and groups match CampaignAudience values: a recipient list is used by the
    # campaigns with that audience. A product list fills any formatted campaign's products.
    CONTACTS = 'contacts', 'Contacts'
    GROUPS = 'groups', 'Groups'
    PRODUCTS = 'products', 'Products'


class CampaignList(models.Model):
    """A saved, reusable campaign list: recipients (kind contacts or groups) or products
    (kind products). Lists belong to a company; applying one to a campaign copies its
    members into the campaign's recipients or product rows."""

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='campaign_lists')
    kind = models.CharField(max_length=20, choices=CampaignListKind.choices, db_index=True)
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


class CampaignListProduct(models.Model):
    campaign_list = models.ForeignKey(CampaignList, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey('trading.Product', on_delete=models.CASCADE, related_name='campaign_list_rows')
    added_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_campaign_list_product'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['campaign_list', 'product'], name='unique_campaign_list_product'),
        ]
