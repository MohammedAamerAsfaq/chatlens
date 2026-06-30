from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0006_add_auto_download_media'),
    ]

    operations = [
        migrations.CreateModel(
            name='DroppedMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('msg_id', models.CharField(blank=True, max_length=255, null=True)),
                ('raw_jid', models.CharField(blank=True, max_length=255, null=True)),
                ('from_me', models.BooleanField(null=True)),
                ('has_message', models.BooleanField(default=False)),
                ('reason', models.CharField(max_length=100)),
                ('raw_key', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dropped_messages',
                    to='whatsapp_bridge.whatsappaccount',
                )),
            ],
            options={
                'db_table': 'whatsapp_dropped_message',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='droppedmessage',
            index=models.Index(fields=['account', 'created_at'], name='whatsapp_dr_account_idx'),
        ),
    ]
