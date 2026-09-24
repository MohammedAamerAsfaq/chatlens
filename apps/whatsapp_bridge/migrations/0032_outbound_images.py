from django.db import migrations, models
import django.db.models.deletion
import apps.whatsapp_bridge.models.outbound_asset
import uuid


class Migration(migrations.Migration):
    dependencies = [('whatsapp_bridge', '0031_outbound_execution')]

    operations = [
        migrations.CreateModel(
            name='OutboundAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('storage_key', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('file', models.FileField(upload_to=apps.whatsapp_bridge.models.outbound_asset.outbound_asset_path)),
                ('original_filename', models.CharField(max_length=255)),
                ('mime_type', models.CharField(max_length=100)),
                ('size_bytes', models.PositiveIntegerField()),
                ('sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_assets', to='tenancy.company')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_assets_uploaded', to='auth.user')),
            ],
            options={'db_table': 'whatsapp_outbound_asset', 'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='whatsappaccount', name='image_sending_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='outboundmessage', name='asset',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='messages', to='whatsapp_bridge.outboundasset'),
        ),
    ]
