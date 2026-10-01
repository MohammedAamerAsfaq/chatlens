from django.db import migrations


def seed_settings(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    Settings = apps.get_model('clientpulse', 'ClientPulseSettings')
    Settings.objects.bulk_create(
        [Settings(company_id=company_id) for company_id in Company.objects.values_list('id', flat=True)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [('clientpulse', '0002_clientprofile_clientnote_clientactivity_and_more')]
    operations = [migrations.RunPython(seed_settings, migrations.RunPython.noop)]
