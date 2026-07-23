from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.tenancy.models import Company, CompanyMembership, CommunicationAccount, ConnectionProvider
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService


class TenancySeedMigrationTests(TestCase):
    def test_control_company_exists(self):
        company = Company.objects.get(slug='control-account')
        self.assertEqual(company.company_type, Company.TYPE_CONTROL)
        self.assertEqual(company.industry_type, Company.INDUSTRY_TRADING)

    def test_default_baileys_provider_exists(self):
        provider = ConnectionProvider.objects.get(key='baileys')
        self.assertEqual(provider.channel, ConnectionProvider.CHANNEL_WHATSAPP)
        self.assertTrue(provider.is_default_for_channel)


class CompanyEnrollmentServiceTests(TestCase):
    def test_enroll_company_creates_company_user_and_membership(self):
        result = CompanyEnrollmentService().enroll_company(
            company_name='Acme Trading',
            email='owner@acme.test',
            username='acme_owner',
            password='secret-pass-123',
            industry_type=Company.INDUSTRY_TRADING,
        )

        company = Company.objects.get(pk=result.company_id)
        user = get_user_model().objects.get(pk=result.user_id)
        membership = CompanyMembership.objects.get(pk=result.membership_id)

        self.assertEqual(company.slug, 'acme-trading')
        self.assertEqual(company.industry_type, Company.INDUSTRY_TRADING)
        self.assertEqual(user.username, 'acme_owner')
        self.assertEqual(membership.company_id, company.pk)
        self.assertEqual(membership.user_id, user.pk)
        self.assertEqual(membership.role, CompanyMembership.ROLE_SUPER_USER)

    def test_enroll_company_rejects_duplicate_username(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username='existing_user',
            email='existing@example.com',
            password='pw',
        )

        with self.assertRaisesMessage(ValueError, "Username 'existing_user' already exists"):
            CompanyEnrollmentService().enroll_company(
                company_name='Beta Trading',
                email='beta@example.com',
                username='existing_user',
                password='secret-pass-123',
            )


class CommunicationAccountValidationTests(TestCase):
    def test_channel_must_match_provider_channel(self):
        company = Company.objects.get(slug='control-account')
        provider = ConnectionProvider.objects.get(key='baileys')

        with self.assertRaisesMessage(Exception, 'Provider channel must match communication account channel.'):
            CommunicationAccount.objects.create(
                company=company,
                provider=provider,
                channel=ConnectionProvider.CHANNEL_GMAIL,
                name='Mismatched Account',
            )
