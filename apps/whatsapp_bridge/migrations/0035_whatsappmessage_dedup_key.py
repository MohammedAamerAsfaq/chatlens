from django.db import migrations, models

# Same rule as message_fingerprint.message_dedup_key: inbound, with contact and fingerprint.
BACKFILL_DEDUP_KEY_SQL = """
UPDATE whatsapp_message AS m
SET dedup_key = c.wa_contact_id || ':' || m.content_fingerprint
FROM whatsapp_contact AS c
WHERE m.contact_id = c.id
  AND m.direction = 'inbound'
  AND m.content_fingerprint <> ''
  AND c.wa_contact_id <> ''
"""


class Migration(migrations.Migration):
    dependencies = [('whatsapp_bridge', '0034_ai_cutoffs_and_message_fingerprint')]

    operations = [
        migrations.AddField(
            model_name='whatsappmessage', name='dedup_key',
            field=models.CharField(blank=True, db_index=True, max_length=128),
        ),
        migrations.RunSQL(BACKFILL_DEDUP_KEY_SQL, migrations.RunSQL.noop),
    ]
