import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SCOPED_PERMISSIONS = {
    'conversations.accounts.view': ('conversations', 'Accounts: View'),
    'conversations.accounts.manage': ('conversations', 'Accounts: Manage'),
    'trading.board.view': ('trading', 'Board: View'),
    'trading.inquiries.update': ('trading', 'Inquiries: Update'),
}


def seed_account_access(apps, schema_editor):
    Permission = apps.get_model('tenancy', 'PermissionDefinition')
    Role = apps.get_model('tenancy', 'CompanyRole')
    Grant = apps.get_model('tenancy', 'CompanyRolePermission')
    Membership = apps.get_model('tenancy', 'CompanyMembership')
    Assignment = apps.get_model('tenancy', 'CommunicationAccountAssignment')
    WhatsAppAccount = apps.get_model('whatsapp_bridge', 'WhatsAppAccount')

    definitions = {}
    for code, (area, label) in SCOPED_PERMISSIONS.items():
        definitions[code], _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                'area': area,
                'label': label,
                'supports_scope': True,
                'is_sensitive': code == 'conversations.accounts.manage',
                'is_active': True,
            },
        )

    view_roles = {'super_user', 'admin', 'manager', 'user', 'viewer', 'campaign_operator'}
    management_roles = {'super_user', 'admin'}
    for role in Role.objects.select_related('company').iterator():
        codes = set()
        if role.key in view_roles:
            codes.add('conversations.accounts.view')
        if role.key in management_roles:
            codes.add('conversations.accounts.manage')
        if role.key in {'super_user', 'admin', 'manager', 'user', 'viewer'}:
            codes.add('trading.board.view')
        if role.key in {'super_user', 'admin', 'manager', 'user'}:
            codes.add('trading.inquiries.update')
        for code in codes:
            scope = 'assigned' if role.key in {'user', 'viewer', 'campaign_operator'} else 'all'
            Grant.objects.update_or_create(
                company_id=role.company_id,
                role_id=role.pk,
                permission_id=definitions[code].pk,
                defaults={'record_scope': scope},
            )

    accounts = WhatsAppAccount.objects.exclude(communication_account_id=None).exclude(owner_id=None)
    for account in accounts.iterator():
        membership = Membership.objects.filter(
            company_id=account.communication_account.company_id,
            user_id=account.owner_id,
            is_active=True,
        ).first()
        if membership:
            Assignment.objects.update_or_create(
                company_id=membership.company_id,
                communication_account_id=account.communication_account_id,
                membership_id=membership.pk,
                defaults={'access_level': 'owner', 'is_active': True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ('tenancy', '0013_add_real_estate_permissions'),
        ('whatsapp_bridge', '0034_ai_cutoffs_and_message_fingerprint'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunicationAccountAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_level', models.CharField(choices=[('owner', 'Account owner'), ('member', 'Assigned member')], default='member', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='communication_account_assignments_created', to=settings.AUTH_USER_MODEL)),
                ('communication_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_assignments', to='tenancy.communicationaccount')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='communication_account_assignments', to='tenancy.company')),
                ('membership', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='communication_account_assignments', to='tenancy.companymembership')),
            ],
            options={'db_table': 'tenant_communication_account_assignment'},
        ),
        migrations.AddConstraint(
            model_name='communicationaccountassignment',
            constraint=models.UniqueConstraint(fields=('communication_account', 'membership'), name='unique_communication_account_assignment'),
        ),
        migrations.AddIndex(
            model_name='communicationaccountassignment',
            index=models.Index(fields=['company', 'membership', 'is_active'], name='tenant_comm_company_806a23_idx'),
        ),
        migrations.AddIndex(
            model_name='communicationaccountassignment',
            index=models.Index(fields=['company', 'communication_account', 'is_active'], name='tenant_comm_company_ef35b2_idx'),
        ),
        migrations.RunPython(seed_account_access, migrations.RunPython.noop),
    ]
