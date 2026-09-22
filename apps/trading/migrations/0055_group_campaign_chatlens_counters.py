from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0054_group_campaign_message_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyinginquirygroup',
            name='chatlens_click_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='buyinginquirygroup',
            name='last_chatlens_clicked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sellingoffergroup',
            name='chatlens_click_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='sellingoffergroup',
            name='last_chatlens_clicked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
