from django.db import migrations


def seed_initial_tenancy_data(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    CompanyMembership = apps.get_model('tenancy', 'CompanyMembership')
    ConnectionProvider = apps.get_model('tenancy', 'ConnectionProvider')
    User = apps.get_model('auth', 'User')

    control_company, _ = Company.objects.get_or_create(
        slug='control-account',
        defaults={
            'name': 'Control Account',
            'company_type': 'control',
            'industry_type': 'trading',
            'is_active': True,
        },
    )

    baileys_provider, created = ConnectionProvider.objects.get_or_create(
        key='baileys',
        defaults={
            'name': 'Baileys WhatsApp Worker',
            'channel': 'whatsapp',
            'provider_type': 'node_worker',
            'is_active': True,
            'is_default_for_channel': True,
            'capabilities': [
                'receive_messages',
                'history_sync',
                'contacts_sync',
                'group_sync',
                'session_qr_link',
            ],
        },
    )
    if not created and not baileys_provider.is_default_for_channel:
        baileys_provider.is_default_for_channel = True
        baileys_provider.save(update_fields=['is_default_for_channel', 'updated_at'])

    superusers = User.objects.filter(is_superuser=True)
    for user in superusers.iterator():
        CompanyMembership.objects.get_or_create(
            company=control_company,
            user=user,
            defaults={
                'role': 'super_user',
                'is_active': True,
            },
        )


def noop_reverse(apps, schema_editor):
    # Seed data should remain in place once created.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_initial_tenancy_data, noop_reverse),
    ]
