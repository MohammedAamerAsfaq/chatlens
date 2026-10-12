from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.ai_providers.models import AIProviderConfig
from apps.queue_management.models import QueueDefinition
from apps.real_estate.models import (
    ActivityType,
    ClassificationDecision,
    ClassificationStatus,
    RealEstateOpportunity,
    RealEstatePromptConfig,
    RealEstateSettings,
)
from apps.real_estate.services.classification_contract import outcome_for_decision
from apps.tenancy.models import Company, CompanyRolePermission
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService


class RealEstateFoundationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Real Estate One',
            slug='real-estate-one',
            industry_type=Company.INDUSTRY_REAL_ESTATE,
        )

    def test_activity_contract_has_exactly_four_values(self):
        self.assertEqual(
            set(ActivityType.values),
            {'buying', 'selling', 'leasing_inquiry', 'leasing_offer'},
        )

    def test_ai_decisions_map_to_one_persistence_outcome(self):
        buying = outcome_for_decision(ClassificationDecision.BUYING)
        review = outcome_for_decision(ClassificationDecision.NEEDS_REVIEW)
        self.assertEqual(buying.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(buying.activity_type, ActivityType.BUYING)
        self.assertEqual(review.status, ClassificationStatus.NEEDS_REVIEW)
        self.assertIsNone(review.activity_type)
        with self.assertRaises(ValueError):
            outcome_for_decision('leasing')

    def test_classified_opportunity_requires_activity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RealEstateOpportunity.objects.create(
                company=self.company,
                classification_status=ClassificationStatus.CLASSIFIED,
                first_seen_at=timezone.now(),
            )

    def test_review_opportunity_rejects_activity(self):
        opportunity = RealEstateOpportunity(
            company=self.company,
            classification_status=ClassificationStatus.NEEDS_REVIEW,
            activity_type=ActivityType.BUYING,
            first_seen_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            opportunity.full_clean()

    def test_prompt_target_must_belong_to_company(self):
        other = Company.objects.create(name='Real Estate Two', slug='real-estate-two')
        agent = AIProviderConfig.objects.create(
            company=other,
            display_name='Other Agent',
            provider=AIProviderConfig.PROVIDER_OPENAI,
            capability=AIProviderConfig.CAPABILITY_AGENT,
            api_key='test',
            model='test-model',
        )
        prompt = RealEstatePromptConfig(
            company=self.company,
            key=RealEstatePromptConfig.KEY_GATE,
            label='Gate',
            body='Classify the message.',
            agent_config=agent,
        )
        with self.assertRaises(ValidationError):
            prompt.full_clean()

    def test_real_estate_queues_are_independently_configured(self):
        queues = QueueDefinition.objects.filter(name__startswith='real_estate_')
        self.assertSetEqual(
            set(queues.values_list('name', flat=True)),
            {
                'real_estate_gate',
                'real_estate_extract',
                'real_estate_match',
                'real_estate_maintenance',
                'real_estate_embeddings',
            },
        )
        self.assertTrue(all(queue.task_timeout_seconds == 300 for queue in queues))

    def test_real_estate_enrollment_seeds_required_settings(self):
        result = CompanyEnrollmentService().enroll_company(
            company_name='New Property Company',
            email='owner@property.test',
            username='property_owner',
            password='secret-pass-123',
            industry_type=Company.INDUSTRY_REAL_ESTATE,
        )
        settings = RealEstateSettings.objects.get(company_id=result.company_id)
        self.assertEqual(settings.gate_mode, RealEstateSettings.GATE_OBSERVATIONAL)
        from apps.real_estate.models import PropertyType
        self.assertTrue(PropertyType.objects.filter(
            company_id=result.company_id, code='apartment', is_active=True,
        ).exists())
        self.assertTrue(CompanyRolePermission.objects.filter(
            company_id=result.company_id,
            role__key='super_user',
            permission__code='real_estate.properties.manage',
        ).exists())
