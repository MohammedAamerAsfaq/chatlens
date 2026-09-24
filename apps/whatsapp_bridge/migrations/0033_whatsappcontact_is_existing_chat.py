from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('whatsapp_bridge', '0032_outbound_images')]

    operations = [
        migrations.AddField(
            model_name='whatsappcontact',
            name='is_existing_chat',
            field=models.BooleanField(default=True),
        ),
    ]
