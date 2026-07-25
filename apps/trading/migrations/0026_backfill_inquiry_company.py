from django.db import migrations


def backfill_inquiry_company(apps, schema_editor):
    Inquiry = apps.get_model('trading', 'Inquiry')

    rows = (
        Inquiry.objects
        .filter(company__isnull=True, account__communication_account__company__isnull=False)
        .values_list('pk', 'account__communication_account__company_id')
    )
    for inquiry_id, company_id in rows.iterator():
        Inquiry.objects.filter(pk=inquiry_id, company__isnull=True).update(company_id=company_id)


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0025_tenant_owned_trading_configuration'),
    ]

    operations = [
        migrations.RunPython(backfill_inquiry_company, migrations.RunPython.noop),
    ]
