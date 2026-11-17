"""Every API change must be refused to a member whose roles grant no permissions.

Access is decided per endpoint from role permissions (there is no blanket role rule
any more), so an endpoint that forgets its permission check would let anyone in the
company change things. This walks every /api/ route and sends every write method as
such a member, signed in through the real session and middleware, and fails on any
response that got past authorization.

OPEN_TO_EVERY_MEMBER lists the few writes that are deliberately not permission-gated,
each with the reason.
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver

from apps.tenancy.models import Company, CompanyMembership, CompanyRole, MembershipRoleAssignment
from apps.tenancy.services.role_seed import seed_company_roles

WRITE_METHODS = ('post', 'put', 'patch', 'delete')
DENIED = {401, 403, 404, 405}

OPEN_TO_EVERY_MEMBER = {
    # Signing in and out, choosing a company and editing one's own account/preferences.
    r'^/api/auth/(login|logout|select-company|account|preferences|me)/$',
    # Assignment to the account is the authorization (see WhatsAppAccountViewSet.toggle_ai).
    r'^/api/accounts/999999/toggle-ai/$',
    # A read sent as POST (the query is the body); results are limited to the member's visible accounts.
    r'^/api/intelligence/search/$',
    # Machine-to-machine endpoints authenticated by their own keys, not by a member session.
    r'^/api/internal/',
    r'^/api/external/',
}


def _walk(patterns, prefix=''):
    for p in patterns:
        regex = prefix + str(p.pattern.regex.pattern).lstrip('^').rstrip('$').replace('\\Z', '')
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, regex)
        elif isinstance(p, URLPattern):
            yield regex


def _concrete(regex):
    path = re.sub(r'\(\?P<[^>]+>[^)]*\)', '999999', regex)
    path = path.replace('\\.', '.').replace('\\/', '/').replace('\\-', '-')
    path = re.sub(r'\(\?:[^)]*\)\??', '', path)
    if any(ch in path for ch in '()[]*+?\\'):
        return None
    return '/' + path


def api_paths():
    paths = {_concrete(regex) for regex in _walk(get_resolver().url_patterns)}
    return sorted(path for path in paths if path and path.startswith('/api/'))


class NoPermissionMemberCannotChangeAnything(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Locked', slug='locked', industry_type='trading')
        seed_company_roles(cls.company)
        empty = CompanyRole.objects.create(company=cls.company, key='nothing', name='Nothing')
        cls.user = get_user_model().objects.create_user(username='nobody', password='x')
        membership = CompanyMembership.objects.create(company=cls.company, user=cls.user)
        MembershipRoleAssignment.objects.create(company=cls.company, membership=membership, role=empty)

    def test_every_open_entry_names_a_real_route(self):
        paths = api_paths()
        stale = [pattern for pattern in OPEN_TO_EVERY_MEMBER if not any(re.search(pattern, path) for path in paths)]
        self.assertEqual(stale, [], 'OPEN_TO_EVERY_MEMBER entries that match no route')

    def test_every_write_is_refused(self):
        open_patterns = [re.compile(pattern) for pattern in OPEN_TO_EVERY_MEMBER]
        leaks = []
        no_network = mock.patch('requests.sessions.Session.request', side_effect=ConnectionError('no network in tests'))
        no_celery = mock.patch('celery.app.task.Task.apply_async', return_value=None)
        with no_network, no_celery:
            for path in api_paths():
                if any(pattern.search(path) for pattern in open_patterns):
                    continue
                for method in WRITE_METHODS:
                    self.client.force_login(self.user)
                    try:
                        with transaction.atomic():
                            response = getattr(self.client, method)(path, data={}, content_type='application/json')
                            transaction.set_rollback(True)
                        status = response.status_code
                    except Exception as exc:  # noqa: BLE001 - reaching the view at all is the leak
                        status = f'{type(exc).__name__}'
                    if status not in DENIED:
                        leaks.append(f'{method.upper()} {path} -> {status}')
        self.assertEqual(leaks, [], 'Writes that a member with no permissions got past authorization')
