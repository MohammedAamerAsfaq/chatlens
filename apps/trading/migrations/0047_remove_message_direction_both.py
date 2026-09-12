from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('trading', '0046_aiparsev2log_gatepass_fields')]

    operations = [
        migrations.AlterField(
            model_name='messageclassification',
            name='inquiry_type',
            field=models.CharField(
                blank=True,
                choices=[('buy', 'Buy'), ('sell', 'Sell')],
                max_length=10,
            ),
        ),
    ]
