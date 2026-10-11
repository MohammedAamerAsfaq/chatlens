from django.core.exceptions import ValidationError
from django.db import models


class RealEstatePromptConfig(models.Model):
    KEY_GATE = 'gate'
    KEY_EXTRACTION = 'extraction'
    KEY_MATCH_RERANK = 'match_rerank'
    KEY_CHOICES = [
        (KEY_GATE, 'Real Estate GatePass'),
        (KEY_EXTRACTION, 'Real Estate Classification and Extraction'),
        (KEY_MATCH_RERANK, 'Real Estate Match Reranking'),
    ]

    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='real_estate_prompt_configs',
    )
    key = models.CharField(max_length=100, choices=KEY_CHOICES)
    label = models.CharField(max_length=200)
    body = models.TextField()
    agent_config = models.ForeignKey(
        'ai_providers.AIProviderConfig',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='real_estate_prompt_configs',
        limit_choices_to={'capability': 'agent'},
    )
    kiwi_router = models.ForeignKey(
        'ai_providers.KiwiRouter',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='real_estate_prompt_configs',
        limit_choices_to={'capability': 'agent'},
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_prompt_config'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'key'],
                name='real_estate_prompt_company_key_uniq',
            ),
            models.CheckConstraint(
                condition=models.Q(agent_config__isnull=True) | models.Q(kiwi_router__isnull=True),
                name='real_estate_prompt_single_target',
            ),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        super().clean()
        errors = {}
        if self.agent_config_id and self.agent_config.company_id != self.company_id:
            errors['agent_config'] = 'The selected AI agent must belong to this company.'
        elif self.agent_config_id and self.agent_config.capability != 'agent':
            errors['agent_config'] = 'The selected provider must be a General AI Agent.'
        if self.kiwi_router_id and self.kiwi_router.company_id != self.company_id:
            errors['kiwi_router'] = 'The selected KiwiRouter must belong to this company.'
        elif self.kiwi_router_id and self.kiwi_router.capability != 'agent':
            errors['kiwi_router'] = 'The selected router must support General AI Agent requests.'
        if self.agent_config_id and self.kiwi_router_id:
            errors['kiwi_router'] = 'Select either a direct AI agent or a KiwiRouter, not both.'
        if errors:
            raise ValidationError(errors)

    @classmethod
    def get_for_company(cls, company, key):
        return cls.objects.select_related('agent_config', 'kiwi_router').filter(
            company=company,
            key=key,
        ).first()
