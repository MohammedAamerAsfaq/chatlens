from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0005_company_ai_parsing_enabled')]

    operations = [
        migrations.AddField(
            model_name='company',
            name='enforce_validity_period',
            field=models.BooleanField(
                default=False,
                help_text='Block company access outside the configured validity period.',
            ),
        ),
    ]
