from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('trading', '0055_group_campaign_chatlens_counters')]

    operations = [
        migrations.AddField(
            model_name='buyinginquirysupplier',
            name='chatlens_click_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='buyinginquirysupplier',
            name='last_chatlens_clicked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sellingoffercustomer',
            name='chatlens_click_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='sellingoffercustomer',
            name='last_chatlens_clicked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
