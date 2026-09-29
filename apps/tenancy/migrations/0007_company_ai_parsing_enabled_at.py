from django.db import migrations, models
from django.utils import timezone


def initialize_cutoffs(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    Company.objects.filter(ai_parsing_enabled=True).update(ai_parsing_enabled_at=timezone.now())
    Company.objects.filter(ai_parsing_enabled=False).update(ai_parsing_enabled_at=None)


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0006_company_enforce_validity_period')]

    operations = [
        migrations.AddField(
            model_name='company',
            name='ai_parsing_enabled_at',
            field=models.DateTimeField(blank=True, default=timezone.now, null=True),
        ),
        migrations.RunPython(initialize_cutoffs, migrations.RunPython.noop),
    ]
