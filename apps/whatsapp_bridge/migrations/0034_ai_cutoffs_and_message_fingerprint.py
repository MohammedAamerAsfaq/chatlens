from django.db import migrations, models
from django.utils import timezone


def initialize_account_cutoffs(apps, schema_editor):
    Account = apps.get_model('whatsapp_bridge', 'WhatsAppAccount')
    Chat = apps.get_model('whatsapp_bridge', 'WhatsAppChat')
    Account.objects.filter(ai_parsing_enabled=True).update(ai_parsing_enabled_at=timezone.now())
    Account.objects.filter(ai_parsing_enabled=False).update(ai_parsing_enabled_at=None)
    Chat.objects.filter(ai_parsing=True).update(ai_parsing_enabled_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('whatsapp_bridge', '0033_whatsappcontact_is_existing_chat')]

    operations = [
        migrations.AddField(
            model_name='whatsappaccount', name='ai_parsing_enabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='whatsappchat', name='ai_parsing_enabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='whatsappmessage', name='content_fingerprint',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.RunPython(initialize_account_cutoffs, migrations.RunPython.noop),
    ]
