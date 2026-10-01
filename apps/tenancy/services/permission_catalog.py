SCOPE_ALL = 'all'
SCOPE_ASSIGNED = 'assigned'


def _permission(code, *, scoped=False, sensitive=False):
    area, resource, action = code.split('.', 2)
    return {
        'code': code,
        'area': area,
        'label': f'{resource.replace("_", " ").title()}: {action.replace("_", " ").title()}',
        'supports_scope': scoped,
        'is_sensitive': sensitive,
    }


PERMISSION_SPECS = [
    _permission('conversations.chats.view', scoped=True),
    _permission('conversations.messages.view', scoped=True),
    _permission('conversations.messages.send', scoped=True, sensitive=True),
    _permission('conversations.contacts.update', scoped=True),
    _permission('conversations.accounts.manage', sensitive=True),
    _permission('trading.board.view'),
    _permission('trading.inquiries.update'),
    _permission('trading.matches.manage'),
    _permission('trading.products.view'),
    _permission('trading.products.manage'),
    _permission('trading.automation.manage', sensitive=True),
    _permission('campaigns.campaigns.view'),
    _permission('campaigns.campaigns.create'),
    _permission('campaigns.campaigns.update'),
    _permission('campaigns.campaigns.delete'),
    _permission('campaigns.messages.send', sensitive=True),
    _permission('campaigns.audiences.manage'),
    _permission('clientpulse.clients.view', scoped=True),
    _permission('clientpulse.clients.create'),
    _permission('clientpulse.clients.update', scoped=True),
    _permission('clientpulse.clients.archive', scoped=True),
    _permission('clientpulse.notes.manage', scoped=True),
    _permission('clientpulse.reminders.view', scoped=True),
    _permission('clientpulse.reminders.manage', scoped=True),
    _permission('clientpulse.sequences.view'),
    _permission('clientpulse.sequences.manage', sensitive=True),
    _permission('clientpulse.messages.send_manual', scoped=True, sensitive=True),
    _permission('clientpulse.messages.send_automated', sensitive=True),
    _permission('clientpulse.contacts.merge', sensitive=True),
    _permission('clientpulse.consent.manage', scoped=True, sensitive=True),
    _permission('clientpulse.reports.view', scoped=True),
    _permission('clientpulse.data.export', sensitive=True),
    _permission('integrations.connections.view'),
    _permission('integrations.connections.manage', sensitive=True),
    _permission('integrations.sync.execute', sensitive=True),
    _permission('integrations.sync.view_history'),
    _permission('integrations.conflicts.resolve', sensitive=True),
    _permission('reports.company.view'),
    _permission('reports.company.export', sensitive=True),
    _permission('tasks.company.view'),
    _permission('tasks.company.retry', sensitive=True),
    _permission('settings.company.view'),
    _permission('settings.company.manage', sensitive=True),
    _permission('users.memberships.view'),
    _permission('users.memberships.manage', sensitive=True),
    _permission('users.roles.view'),
    _permission('users.roles.manage', sensitive=True),
    _permission('sending.policy.manage', sensitive=True),
    _permission('automation.company.enable', sensitive=True),
]

ALL_CODES = {item['code'] for item in PERMISSION_SPECS}

ROLE_SPECS = {
    'super_user': {'name': 'Owner', 'description': 'Full company ownership and administration.', 'owner': True},
    'admin': {'name': 'Administrator', 'description': 'Company administration without ownership transfer.'},
    'manager': {'name': 'Manager', 'description': 'Company-wide operational management.'},
    'user': {'name': 'Sales Agent', 'description': 'Assigned operational and customer work.'},
    'viewer': {'name': 'Viewer', 'description': 'Read-only access to granted areas.'},
    'campaign_operator': {'name': 'Campaign Operator', 'description': 'Campaign creation and sending.'},
    'integration_manager': {'name': 'Integration Manager', 'description': 'External connection and sync management.'},
}

VIEW_CODES = {code for code in ALL_CODES if code.endswith(('.view', '.view_history'))}
MANAGER_EXCLUDED_PREFIXES = ('users.', 'integrations.', 'settings.', 'sending.')
MANAGER_CODES = {
    code for code in ALL_CODES
    if not code.startswith(MANAGER_EXCLUDED_PREFIXES)
    and code not in {'automation.company.enable', 'clientpulse.messages.send_automated', 'tasks.company.retry'}
}
USER_CODES = {
    'conversations.chats.view', 'conversations.messages.view', 'conversations.messages.send',
    'conversations.contacts.update', 'trading.board.view', 'trading.inquiries.update',
    'trading.products.view', 'campaigns.campaigns.view', 'clientpulse.clients.view',
    'clientpulse.clients.update', 'clientpulse.notes.manage', 'clientpulse.reminders.view',
    'clientpulse.reminders.manage', 'clientpulse.sequences.view',
    'clientpulse.messages.send_manual', 'clientpulse.reports.view', 'reports.company.view',
}
CAMPAIGN_CODES = {
    code for code in ALL_CODES if code.startswith('campaigns.')
} | {'trading.products.view', 'conversations.chats.view', 'conversations.messages.send', 'reports.company.view'}
INTEGRATION_CODES = {
    code for code in ALL_CODES if code.startswith('integrations.')
} | {'tasks.company.view'}

ROLE_GRANTS = {
    'super_user': ALL_CODES,
    'admin': ALL_CODES,
    'manager': MANAGER_CODES,
    'user': USER_CODES,
    'viewer': VIEW_CODES,
    'campaign_operator': CAMPAIGN_CODES,
    'integration_manager': INTEGRATION_CODES,
}


def default_scope(role_key, permission_spec):
    if role_key == 'user' and permission_spec['supports_scope']:
        return SCOPE_ASSIGNED
    return SCOPE_ALL
