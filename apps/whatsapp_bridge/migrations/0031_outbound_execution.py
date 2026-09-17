import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenancy', '0005_company_ai_parsing_enabled'),
        ('whatsapp_bridge', '0030_whatsappaccountcapacity'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutboundMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destination_jid', models.CharField(max_length=255)),
                ('canonical_recipient_key', models.CharField(db_index=True, max_length=255)),
                ('destination_type', models.CharField(blank=True, max_length=40)),
                ('content_type', models.CharField(default='text', max_length=20)),
                ('content_payload', models.JSONField(default=dict)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('deferred', 'Deferred'), ('preflight_blocked', 'Preflight Blocked'), ('sending', 'Sending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('unknown', 'Unknown')], db_index=True, default='queued', max_length=30)),
                ('status_reason', models.CharField(blank=True, max_length=100)),
                ('idempotency_key', models.CharField(max_length=255)),
                ('provider_message_id', models.CharField(default=uuid.uuid4, max_length=100, unique=True)),
                ('correlation_id', models.CharField(db_index=True, max_length=255)),
                ('new_chat_state', models.CharField(default='unknown', max_length=30)),
                ('new_chat_confidence', models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
                ('new_chat_reason', models.CharField(blank=True, max_length=100)),
                ('permission_snapshot', models.JSONField(blank=True, default=dict)),
                ('settings_snapshot', models.JSONField(blank=True, default=dict)),
                ('provider_response', models.JSONField(blank=True, default=dict)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('eligible_at', models.DateTimeField(blank=True, null=True)),
                ('dispatch_started_at', models.DateTimeField(blank=True, null=True)),
                ('provider_accepted_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('last_error_code', models.CharField(blank=True, max_length=100)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_messages', to='tenancy.company')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_messages_requested', to=settings.AUTH_USER_MODEL)),
                ('whatsapp_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_messages', to='whatsapp_bridge.whatsappaccount')),
            ],
            options={'db_table': 'whatsapp_outbound_message', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OutboundMessageEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=50)), ('actor', models.CharField(blank=True, max_length=255)),
                ('attempt_number', models.PositiveIntegerField(default=0)), ('detail', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)), ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='whatsapp_bridge.outboundmessage')),
            ],
            options={'db_table': 'whatsapp_outbound_message_event', 'ordering': ['created_at', 'id']},
        ),
        migrations.CreateModel(
            name='OutboundAccountState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_dispatch_started_at', models.DateTimeField(blank=True, null=True)),
                ('in_flight_count', models.PositiveIntegerField(default=0)), ('lease_version', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('whatsapp_account', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_state', to='whatsapp_bridge.whatsappaccount')),
            ], options={'db_table': 'whatsapp_outbound_account_state'},
        ),
        migrations.CreateModel(
            name='OutboundRecipientState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canonical_recipient_key', models.CharField(max_length=255)),
                ('last_dispatch_started_at', models.DateTimeField(blank=True, null=True)),
                ('in_flight_count', models.PositiveIntegerField(default=0)), ('updated_at', models.DateTimeField(auto_now=True)),
                ('whatsapp_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_recipient_states', to='whatsapp_bridge.whatsappaccount')),
            ], options={'db_table': 'whatsapp_outbound_recipient_state'},
        ),
        migrations.AddConstraint(model_name='outboundmessage', constraint=models.UniqueConstraint(fields=('company', 'idempotency_key'), name='unique_company_outbound_idempotency')),
        migrations.AddIndex(model_name='outboundmessage', index=models.Index(fields=['whatsapp_account', 'status', 'eligible_at'], name='whatsapp_ou_whatsap_6059aa_idx')),
        migrations.AddConstraint(model_name='outboundrecipientstate', constraint=models.UniqueConstraint(fields=('whatsapp_account', 'canonical_recipient_key'), name='unique_outbound_recipient_state')),
    ]
