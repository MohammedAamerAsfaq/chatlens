from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0049_make_gatepass_audit_fields_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='automationrule',
            name='update_type',
            field=models.CharField(
                choices=[('sale_price', 'Sale Price'), ('qty_cost', 'Qty & Cost')],
                db_index=True,
                default='sale_price',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='automatedpricecapture',
            name='update_type',
            field=models.CharField(
                choices=[('sale_price', 'Sale Price'), ('qty_cost', 'Qty & Cost')],
                db_index=True,
                default='sale_price',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='automatedpricecapture',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', 'Queued'), ('applied', 'Applied'), ('ignored', 'Ignored'),
                    ('test', 'Test match'), ('parse_failed', 'Parse failed'),
                    ('no_priced_items', 'No priced items'),
                    ('no_update_items', 'No update items'), ('apply_failed', 'Apply failed'),
                ],
                default='queued',
                max_length=20,
            ),
        ),
    ]
