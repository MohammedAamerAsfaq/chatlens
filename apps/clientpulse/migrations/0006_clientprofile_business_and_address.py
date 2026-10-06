from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clientpulse', '0005_seed_reminder_schedules'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientprofile', name='company_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='clientprofile', name='job_title',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='clientprofile', name='website',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='clientprofile', name='address_line1',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='clientprofile', name='address_line2',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='clientprofile', name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='clientprofile', name='state_region',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='clientprofile', name='postal_code',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='clientprofile', name='country',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
