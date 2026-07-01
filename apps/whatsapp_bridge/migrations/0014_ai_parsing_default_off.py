from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0013_add_ai_parsing_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='whatsappaccount',
            name='ai_parsing_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
