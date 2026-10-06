from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.clientpulse.models import ClientProfile, ClientTag, ClientTagAssignment
from apps.tenancy.models import Company, CompanyContact, CompanyMembership


class ClientTagApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name='Tags Company', slug='tags-company')
        self.other_company = Company.objects.create(name='Other Tags', slug='other-tags')
        self.user = User.objects.create_user('tags-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        contact = CompanyContact.objects.create(company=self.company, display_name='Tagged Client')
        self.profile = ClientProfile.objects.create(
            company=self.company, contact=contact, created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_reports_assignment_usage(self):
        tag = ClientTag.objects.create(company=self.company, name='VIP', color='#112233')
        ClientTagAssignment.objects.create(
            company=self.company, profile=self.profile, tag=tag, assigned_by=self.user,
        )
        response = self.client.get('/api/clientpulse/tags/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [{
            'id': tag.pk, 'name': 'VIP', 'color': '#112233', 'usage_count': 1,
        }])

    def test_create_validates_name_color_and_company_uniqueness(self):
        response = self.client.post(
            '/api/clientpulse/tags/', {'name': '  Priority   Buyer ', 'color': '#AABBCC'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['name'], 'Priority Buyer')
        self.assertEqual(response.data['color'], '#aabbcc')
        duplicate = self.client.post('/api/clientpulse/tags/', {'name': 'priority buyer'}, format='json')
        self.assertEqual(duplicate.status_code, 400)
        invalid = self.client.post(
            '/api/clientpulse/tags/', {'name': 'Invalid Color', 'color': 'red'}, format='json',
        )
        self.assertEqual(invalid.status_code, 400)

    def test_update_renames_and_recolors_tag(self):
        tag = ClientTag.objects.create(company=self.company, name='Warm', color='#123456')
        response = self.client.patch(
            f'/api/clientpulse/tags/{tag.pk}/', {'name': 'Hot Lead', 'color': '#FEDCBA'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        tag.refresh_from_db()
        self.assertEqual((tag.name, tag.color), ('Hot Lead', '#fedcba'))

    def test_update_rejects_name_owned_by_deleted_tag(self):
        tag = ClientTag.objects.create(company=self.company, name='Current')
        ClientTag.objects.create(company=self.company, name='Reserved', is_active=False)
        response = self.client.patch(
            f'/api/clientpulse/tags/{tag.pk}/', {'name': 'reserved'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        tag.refresh_from_db()
        self.assertEqual(tag.name, 'Current')

    def test_delete_deactivates_tag_and_removes_assignments(self):
        tag = ClientTag.objects.create(company=self.company, name='Temporary')
        ClientTagAssignment.objects.create(
            company=self.company, profile=self.profile, tag=tag, assigned_by=self.user,
        )
        response = self.client.delete(f'/api/clientpulse/tags/{tag.pk}/')
        self.assertEqual(response.status_code, 204)
        tag.refresh_from_db()
        self.assertFalse(tag.is_active)
        self.assertFalse(ClientTagAssignment.objects.filter(tag=tag).exists())
        self.assertEqual(self.client.get('/api/clientpulse/tags/').data, [])

    def test_create_reactivates_deleted_tag(self):
        tag = ClientTag.objects.create(
            company=self.company, name='Returning', color='#111111', is_active=False,
        )
        response = self.client.post(
            '/api/clientpulse/tags/', {'name': 'Returning', 'color': '#abcdef'}, format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['id'], tag.pk)
        tag.refresh_from_db()
        self.assertTrue(tag.is_active)
        self.assertEqual(tag.color, '#abcdef')

    def test_foreign_company_tag_is_hidden(self):
        tag = ClientTag.objects.create(company=self.other_company, name='Foreign')
        response = self.client.patch(
            f'/api/clientpulse/tags/{tag.pk}/', {'name': 'Unsafe'}, format='json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(tag.name, 'Foreign')
