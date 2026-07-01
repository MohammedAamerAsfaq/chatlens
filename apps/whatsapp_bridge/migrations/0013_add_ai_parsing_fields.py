from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0012_rename_whatsapp_dr_account_idx_whatsapp_dr_account_fadf6b_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappaccount',
            name='ai_parsing_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='whatsappchat',
            name='ai_parsing',
            field=models.BooleanField(null=True, blank=True),
        ),
    ]
