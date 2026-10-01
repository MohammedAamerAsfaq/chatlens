from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.clientpulse.models import ContactMergeCandidate
from apps.clientpulse.services.contact_linking import (
    generate_identity_merge_candidates,
    link_whatsapp_contact,
    unlink_whatsapp_contact,
)
from apps.tenancy.models import (
    CommunicationAccount,
    Company,
    CompanyContact,
    CompanyContactIdentity,
    ConnectionProvider,
)
from apps.tenancy.services.identity_normalization import normalize_identity
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppContact


class IdentityNormalizationTests(TestCase):
    def test_normalizes_supported_exact_identity_types(self):
        self.assertEqual(normalize_identity('email', ' User@Example.COM '), 'user@example.com')
        self.assertEqual(normalize_identity('phone', '+971 50-123 4567'), '971501234567')
        self.assertEqual(
            normalize_identity('whatsapp_jid', '971501234567:4@S.WHATSAPP.NET'),
            '971501234567@s.whatsapp.net',
        )

    def test_identity_derives_company_and_rejects_cross_company_assignment(self):
        company = Company.objects.create(name='Identity Co', slug='identity-co')
        other = Company.objects.create(name='Other Identity Co', slug='other-identity-co')
        contact = CompanyContact.objects.create(company=company, display_name='Test')
        identity = CompanyContactIdentity.objects.create(
            contact=contact, identity_type='phone', value='+971 50 123 4567',
        )
        self.assertEqual(identity.company, company)
        self.assertEqual(identity.normalized_value, '971501234567')
        identity.company = other
        with self.assertRaisesMessage(ValueError, 'must match'):
            identity.save()


class WhatsAppContactLinkingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Link Co', slug='link-co')
        provider, _ = ConnectionProvider.objects.get_or_create(
            key='test-baileys',
            defaults={'name': 'Test Baileys', 'channel': ConnectionProvider.CHANNEL_WHATSAPP},
        )
        communication_account = CommunicationAccount.objects.create(
            company=self.company,
            provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
            name='Link Account',
        )
        user = get_user_model().objects.create_user('contact-link-user')
        account = WhatsAppAccount.objects.create(
            owner=user, communication_account=communication_account, display_name='Link Account',
        )
        self.whatsapp_contact = WhatsAppContact.objects.create(
            account=account,
            wa_contact_id='971501234567@s.whatsapp.net',
            phone_number='+971 50 123 4567',
            display_name='Remote Contact',
        )

    def _contact_with_phone(self, name):
        contact = CompanyContact.objects.create(company=self.company, display_name=name)
        CompanyContactIdentity.objects.create(
            contact=contact,
            identity_type=CompanyContactIdentity.TYPE_PHONE,
            value='+971501234567',
            is_verified=True,
        )
        return contact

    def test_only_apply_mode_persists_unambiguous_link(self):
        contact = self._contact_with_phone('Exact Match')
        self.assertEqual(link_whatsapp_contact(self.whatsapp_contact).status, 'would_link')
        self.whatsapp_contact.refresh_from_db()
        self.assertIsNone(self.whatsapp_contact.company_contact_id)

        result = link_whatsapp_contact(self.whatsapp_contact, apply=True)
        self.assertEqual(result.contact_id, contact.pk)
        self.whatsapp_contact.refresh_from_db()
        self.assertEqual(self.whatsapp_contact.company_contact_id, contact.pk)

    def test_ambiguous_match_creates_review_candidate_without_linking(self):
        left = self._contact_with_phone('Left Match')
        right = self._contact_with_phone('Right Match')
        result = link_whatsapp_contact(self.whatsapp_contact, apply=True)
        self.assertEqual(result.status, 'ambiguous')
        self.whatsapp_contact.refresh_from_db()
        self.assertIsNone(self.whatsapp_contact.company_contact_id)
        candidate = ContactMergeCandidate.objects.get()
        self.assertEqual((candidate.left_contact_id, candidate.right_contact_id), (left.pk, right.pk))

    def test_duplicate_scan_is_explicit_and_idempotent(self):
        self._contact_with_phone('Duplicate One')
        self._contact_with_phone('Duplicate Two')
        self.assertEqual(generate_identity_merge_candidates(self.company.pk), 1)
        self.assertEqual(ContactMergeCandidate.objects.count(), 0)
        self.assertEqual(generate_identity_merge_candidates(self.company.pk, apply=True), 1)
        self.assertEqual(generate_identity_merge_candidates(self.company.pk, apply=True), 1)
        self.assertEqual(ContactMergeCandidate.objects.count(), 1)

    def test_unlink_is_tenant_checked(self):
        contact = self._contact_with_phone('Linked Contact')
        self.whatsapp_contact.company_contact = contact
        self.whatsapp_contact.save(update_fields=['company_contact', 'updated_at'])
        other = Company.objects.create(name='Unlink Other', slug='unlink-other')
        with self.assertRaisesMessage(ValueError, 'does not belong'):
            unlink_whatsapp_contact(self.whatsapp_contact, company_id=other.pk)
        unlink_whatsapp_contact(self.whatsapp_contact, company_id=self.company.pk)
        self.whatsapp_contact.refresh_from_db()
        self.assertIsNone(self.whatsapp_contact.company_contact_id)

    def test_management_command_is_dry_run_by_default(self):
        self._contact_with_phone('Command Match')
        call_command('link_company_contacts', company_id=self.company.pk)
        self.whatsapp_contact.refresh_from_db()
        self.assertIsNone(self.whatsapp_contact.company_contact_id)
        call_command('link_company_contacts', company_id=self.company.pk, apply=True)
        self.whatsapp_contact.refresh_from_db()
        self.assertIsNotNone(self.whatsapp_contact.company_contact_id)
