from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0024_contactroletag'),
    ]

    operations = [
        migrations.CreateModel(
            name='BaileysEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(blank=True, max_length=64)),
                ('event_type', models.CharField(max_length=100)),
                ('event_stage', models.CharField(choices=[('received', 'Received from Baileys'), ('filtered', 'Filtered before Django'), ('forwarding', 'Forwarding to Django'), ('forwarded', 'Forwarded to Django'), ('failed', 'Failed'), ('history', 'History sync'), ('internal', 'Baileys internal')], max_length=30)),
                ('status', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('failure', 'Failure'), ('skipped', 'Skipped')], max_length=20)),
                ('provider_message_id', models.CharField(blank=True, db_index=True, max_length=255)),
                ('raw_jid', models.CharField(blank=True, max_length=255)),
                ('remote_jid', models.CharField(blank=True, max_length=255)),
                ('participant_jid', models.CharField(blank=True, max_length=255)),
                ('participant_pn', models.CharField(blank=True, max_length=255)),
                ('sender_jid', models.CharField(blank=True, max_length=255)),
                ('sender_number', models.CharField(blank=True, max_length=64)),
                ('push_name', models.CharField(blank=True, max_length=255)),
                ('direction', models.CharField(blank=True, max_length=20)),
                ('message_type', models.CharField(blank=True, max_length=50)),
                ('upsert_type', models.CharField(blank=True, max_length=30)),
                ('reason', models.CharField(blank=True, max_length=120)),
                ('error_message', models.TextField(blank=True)),
                ('raw_key', models.JSONField(blank=True, null=True)),
                ('raw_payload', models.JSONField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='baileys_events', to='whatsapp_bridge.whatsappaccount')),
                ('whatsapp_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='baileys_events', to='whatsapp_bridge.whatsappmessage')),
            ],
            options={
                'db_table': 'whatsapp_baileys_event',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['account', 'created_at'], name='whatsapp_ba_account_8d6d6f_idx'),
                    models.Index(fields=['account', 'provider_message_id'], name='whatsapp_ba_account_d3b22b_idx'),
                    models.Index(fields=['event_stage', 'created_at'], name='whatsapp_ba_event_s_1629bb_idx'),
                    models.Index(fields=['status', 'created_at'], name='whatsapp_ba_status_f02661_idx'),
                    models.Index(fields=['reason', 'created_at'], name='whatsapp_ba_reason_51228b_idx'),
                ],
            },
        ),
    ]
