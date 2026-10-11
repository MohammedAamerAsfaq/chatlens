from django.db import migrations


def add_settings(apps, schema_editor):
    company_model = apps.get_model('tenancy', 'Company')
    settings_model = apps.get_model('real_estate', 'RealEstateSettings')
    for company_id in company_model.objects.filter(
        industry_type='real_estate',
    ).values_list('id', flat=True).iterator():
        settings_model.objects.get_or_create(company_id=company_id)


def remove_settings(apps, schema_editor):
    settings_model = apps.get_model('real_estate', 'RealEstateSettings')
    settings_model.objects.filter(company__industry_type='real_estate').delete()


class Migration(migrations.Migration):
    dependencies = [('real_estate', '0001_initial')]
    operations = [migrations.RunPython(add_settings, remove_settings)]
