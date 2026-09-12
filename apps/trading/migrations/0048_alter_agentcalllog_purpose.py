from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('trading', '0047_remove_message_direction_both')]

    operations = [
        migrations.AlterField(
            model_name='agentcalllog',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('classification', 'Inquiry Classification'),
                    ('product_extraction', 'Product Extraction'),
                    ('match_verification', 'Inquiry Match Verification'),
                    ('inquiry_extraction_v2', 'Inquiry Extraction V2'),
                    ('inquiry_match_v2', 'Inquiry Match Decision V2'),
                    ('inquiry_gate_v2', 'Inquiry GatePass V2'),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
