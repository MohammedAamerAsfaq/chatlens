from django.db import migrations, models
import django.db.models.deletion


def backfill_tenant_owned_configuration(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    PromptConfig = apps.get_model('trading', 'PromptConfig')
    FormattedPriceList = apps.get_model('trading', 'FormattedPriceList')

    company = Company.objects.filter(company_type='control', is_active=True).first()
    if company is None:
        company = Company.objects.filter(is_active=True).order_by('id').first()
    if company is None:
        return

    PromptConfig.objects.filter(company__isnull=True).update(company=company)
    FormattedPriceList.objects.filter(company__isnull=True).update(company=company)


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0003_backfill_existing_tenant_links'),
        ('chatlens_core', '0002_systemsettings_company'),
        ('trading', '0024_inquiry_company_product_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='formattedpricelist',
            name='company',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='formatted_price_list', to='tenancy.company'),
        ),
        migrations.AddField(
            model_name='promptconfig',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prompt_configs', to='tenancy.company'),
        ),
        migrations.AlterField(
            model_name='promptconfig',
            name='key',
            field=models.CharField(max_length=100),
        ),
        migrations.RunPython(backfill_tenant_owned_configuration, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='promptconfig',
            constraint=models.UniqueConstraint(fields=('company', 'key'), name='trading_prompt_company_key_uniq'),
        ),
    ]
