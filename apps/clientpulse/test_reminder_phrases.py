from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.clientpulse.models import ClientReminderPhrase
from apps.tenancy.models import Company
from apps.tenancy.testing import create_member

URL = '/api/clientpulse/reminder-phrases/'


class ReminderPhraseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Phrase Co', slug='phrase-co')
        self.other = Company.objects.create(name='Other Co', slug='other-co')
        self.admin = get_user_model().objects.create_user('phrase-admin')
        create_member(company=self.company, user=self.admin, role='super_user')
        self.agent = get_user_model().objects.create_user('phrase-agent')
        create_member(company=self.company, user=self.agent, role='user')
        self.client = APIClient(); self.client.force_authenticate(self.admin)

    def _create(self, text):
        return self.client.post(URL, {'text': text}, format='json')

    def test_admin_adds_edits_reorders_and_deletes_actions(self):
        first = self._create('  Send   price list ').data
        second = self._create('Sent Hi').data
        self.assertEqual(first['text'], 'Send price list')
        self.assertEqual([first['position'], second['position']], [0, 1])

        response = self.client.patch(f"{URL}{first['id']}/", {'text': 'Send updated price list'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

        response = self.client.post(f'{URL}order/', {'ids': [second['id'], first['id']]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [item['text'] for item in self.client.get(URL).data],
            ['Sent Hi', 'Send updated price list'],
        )

        self.assertEqual(self.client.delete(f"{URL}{second['id']}/").status_code, 204)
        self.assertEqual([item['text'] for item in self.client.get(URL).data], ['Send updated price list'])

    def test_refuses_blank_duplicate_and_incomplete_order(self):
        phrase = self._create('Sent Hi').data
        self.assertEqual(self._create('   ').status_code, 400)
        self.assertEqual(self._create('sent  HI').status_code, 400)
        other = self._create('Send product photos').data
        self.assertEqual(
            self.client.patch(f"{URL}{other['id']}/", {'text': 'SENT HI'}, format='json').status_code, 400,
        )
        self.assertEqual(self.client.post(f'{URL}order/', {'ids': [phrase['id']]}, format='json').status_code, 400)

    def test_agents_read_but_cannot_change_actions(self):
        phrase = self._create('Followed up on order').data
        agent = APIClient(); agent.force_authenticate(self.agent)
        self.assertEqual([item['text'] for item in agent.get(URL).data], ['Followed up on order'])
        self.assertEqual(agent.post(URL, {'text': 'New'}, format='json').status_code, 403)
        self.assertEqual(agent.patch(f"{URL}{phrase['id']}/", {'text': 'x'}, format='json').status_code, 403)
        self.assertEqual(agent.delete(f"{URL}{phrase['id']}/").status_code, 403)

    def test_actions_are_company_scoped(self):
        foreign = ClientReminderPhrase.objects.create(company=self.other, text='Foreign action')
        self.assertEqual(self.client.get(URL).data, [])
        self.assertEqual(self.client.delete(f'{URL}{foreign.pk}/').status_code, 404)
