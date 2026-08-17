from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0004_company_default_classification_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='ai_parsing_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
