from django.db import migrations, models
import django.db.models.deletion


def backfill_system_settings_company(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    SystemSettings = apps.get_model('chatlens_core', 'SystemSettings')

    company = Company.objects.filter(company_type='control', is_active=True).first()
    if company is None:
        company = Company.objects.filter(is_active=True).order_by('id').first()
    if company is None:
        return

    SystemSettings.objects.filter(company__isnull=True).update(company=company)


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0003_backfill_existing_tenant_links'),
        ('chatlens_core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='system_settings', to='tenancy.company'),
        ),
        migrations.AlterField(
            model_name='systemsettings',
            name='key',
            field=models.CharField(max_length=255),
        ),
        migrations.RunPython(backfill_system_settings_company, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='systemsettings',
            constraint=models.UniqueConstraint(fields=('company', 'key'), name='system_setting_company_key_uniq'),
        ),
    ]
