from django.db import migrations


def backfill_existing_tenant_links(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    ConnectionProvider = apps.get_model('tenancy', 'ConnectionProvider')
    CommunicationAccount = apps.get_model('tenancy', 'CommunicationAccount')
    AccountEndpoint = apps.get_model('tenancy', 'AccountEndpoint')
    WhatsAppAccount = apps.get_model('whatsapp_bridge', 'WhatsAppAccount')
    Product = apps.get_model('trading', 'Product')
    Inquiry = apps.get_model('trading', 'Inquiry')

    control_company = Company.objects.get(slug='control-account')
    baileys_provider = ConnectionProvider.objects.get(key='baileys')

    for account in WhatsAppAccount.objects.all().iterator():
        communication_account = account.communication_account
        if communication_account is None:
            derived_name = (
                account.display_name.strip()
                or account.phone_number.strip()
                or f'WhatsApp Account #{account.pk}'
            )
            communication_account, _ = CommunicationAccount.objects.get_or_create(
                company=control_company,
                provider=baileys_provider,
                channel='whatsapp',
                external_account_id=f'legacy-whatsapp-account:{account.pk}',
                defaults={
                    'name': derived_name,
                    'is_active': account.is_active,
                },
            )
            account.communication_account = communication_account

        if account.phone_number:
            endpoint, _ = AccountEndpoint.objects.get_or_create(
                communication_account=communication_account,
                endpoint_type='phone',
                value=account.phone_number,
                defaults={
                    'is_primary': True,
                    'is_active': account.is_active,
                    'metadata': {'source': 'legacy_whatsapp_account'},
                },
            )
            if not account.primary_endpoint_id:
                account.primary_endpoint = endpoint

        update_fields = []
        if account.communication_account_id:
            update_fields.append('communication_account')
        if account.primary_endpoint_id:
            update_fields.append('primary_endpoint')
        if update_fields:
            account.save(update_fields=update_fields)

    Product.objects.filter(company__isnull=True).update(company=control_company)
    Inquiry.objects.filter(company__isnull=True).update(company=control_company)


def noop_reverse(apps, schema_editor):
    # This backfill establishes the forward-compatible tenant ownership mapping.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0002_seed_initial_tenancy_data'),
        ('whatsapp_bridge', '0023_whatsappaccount_communication_account_and_more'),
        ('trading', '0024_inquiry_company_product_company'),
    ]

    operations = [
        migrations.RunPython(backfill_existing_tenant_links, noop_reverse),
    ]
