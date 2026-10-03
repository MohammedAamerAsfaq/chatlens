from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0011_user_company_preference')]

    operations = [
        migrations.AddField(
            model_name='usercompanypreference',
            name='inspinia_config',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
