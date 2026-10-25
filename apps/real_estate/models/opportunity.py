from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from .contracts import ActivityType, ClassificationStatus, MarketScope


class RealEstateOpportunity(models.Model):
    STATUS_NEW = 'new'
    STATUS_QUALIFIED = 'qualified'
    STATUS_MATCHED = 'matched'
    STATUS_CONTACTED = 'contacted'
    STATUS_VIEWING = 'viewing'
    STATUS_NEGOTIATION = 'negotiation'
    STATUS_WON = 'won'
    STATUS_LOST = 'lost'
    STATUS_IRRELEVANT = 'irrelevant'
    STATUS_CHOICES = [
        (value, value.replace('_', ' ').title())
        for value in (
            STATUS_NEW, STATUS_QUALIFIED, STATUS_MATCHED, STATUS_CONTACTED,
            STATUS_VIEWING, STATUS_NEGOTIATION, STATUS_WON, STATUS_LOST,
            STATUS_IRRELEVANT,
        )
    ]

    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='real_estate_opportunities',
    )
    source_message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='real_estate_opportunity',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='real_estate_opportunities',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='real_estate_opportunities',
    )
    company_contact = models.ForeignKey(
        'tenancy.CompanyContact',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='real_estate_opportunities',
    )
    source_chat = models.ForeignKey(
        'whatsapp_bridge.WhatsAppChat',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='real_estate_opportunities',
    )
    inquiry_medium = models.ForeignKey(
        'real_estate.InquiryMedium',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='opportunities',
    )
    source_party_name = models.CharField(max_length=255, blank=True)
    source_contact_detail = models.CharField(max_length=255, blank=True)
    source_reference = models.CharField(max_length=255, blank=True)
    activity_type = models.CharField(
        max_length=30,
        choices=ActivityType.choices,
        null=True,
        blank=True,
    )
    market_scope = models.CharField(
        max_length=20,
        choices=MarketScope.choices,
        default=MarketScope.LOCAL,
    )
    classification_status = models.CharField(
        max_length=30,
        choices=ClassificationStatus.choices,
        default=ClassificationStatus.NEEDS_REVIEW,
    )
    summary = models.TextField(blank=True)
    original_message = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_NEW)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_real_estate_opportunities',
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    matching_complete = models.BooleanField(default=False)
    deduplication_key = models.CharField(max_length=255, blank=True)
    first_seen_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_opportunity'
        ordering = ['-first_seen_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        classification_status=ClassificationStatus.CLASSIFIED,
                        activity_type__isnull=False,
                    )
                    | (
                        ~Q(classification_status=ClassificationStatus.CLASSIFIED)
                        & Q(activity_type__isnull=True)
                    )
                ),
                name='real_estate_classification_activity_valid',
            ),
            models.UniqueConstraint(
                fields=['company', 'deduplication_key'],
                condition=~Q(deduplication_key=''),
                name='real_estate_company_deduplication_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'activity_type', 'status']),
            models.Index(fields=['company', 'classification_status', 'first_seen_at']),
        ]

    def __str__(self):
        return f'{self.company.name} opportunity #{self.pk or "new"}'

    @property
    def is_requirement(self):
        return self.activity_type in ActivityType.requirement_values()

    @property
    def is_property_offer(self):
        return self.activity_type in ActivityType.offer_values()

    def clean(self):
        super().clean()
        errors = {}
        has_activity = bool(self.activity_type)
        if self.classification_status == ClassificationStatus.CLASSIFIED and not has_activity:
            errors['activity_type'] = 'A classified opportunity requires one activity.'
        if self.classification_status != ClassificationStatus.CLASSIFIED and has_activity:
            errors['activity_type'] = 'Review and non-real-estate outcomes cannot have an activity.'
        self._validate_company_links(errors)
        if errors:
            raise ValidationError(errors)

    def _validate_company_links(self, errors):
        linked_accounts = {
            'account': self.account if self.account_id else None,
            'contact': self.contact.account if self.contact_id else None,
            'source_chat': self.source_chat.account if self.source_chat_id else None,
            'source_message': self.source_message.account if self.source_message_id else None,
        }
        for field, account in linked_accounts.items():
            if account and self._account_company_id(account) != self.company_id:
                errors[field] = 'The linked WhatsApp record must belong to this company.'
        if self.contact_id and self.account_id and self.contact.account_id != self.account_id:
            errors['contact'] = 'The WhatsApp contact must belong to the selected account.'
        if self.company_contact_id and self.company_contact.company_id != self.company_id:
            errors['company_contact'] = 'The contact must belong to this company.'
        if self.inquiry_medium_id and self.inquiry_medium.company_id != self.company_id:
            errors['inquiry_medium'] = 'The inquiry medium must belong to this company.'
        if self.source_chat_id and self.account_id and self.source_chat.account_id != self.account_id:
            errors['source_chat'] = 'The source chat must belong to the selected account.'
        if self.source_message_id and self.account_id and self.source_message.account_id != self.account_id:
            errors['source_message'] = 'The source message must belong to the selected account.'
        if self.assigned_to_id:
            from apps.tenancy.models import CompanyMembership

            is_member = CompanyMembership.objects.filter(
                company_id=self.company_id,
                user_id=self.assigned_to_id,
                is_active=True,
            ).exists()
            if not is_member:
                errors['assigned_to'] = 'The assigned user must be an active company member.'

    @staticmethod
    def _account_company_id(account):
        communication = account.communication_account
        return communication.company_id if communication else None
