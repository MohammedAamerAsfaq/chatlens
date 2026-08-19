from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0041_buying_inquiry_workflow_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellingoffer',
            name='color_position',
            field=models.CharField(default='prefix', max_length=10),
        ),
        migrations.AddField(
            model_name='sellingoffer',
            name='flag_position',
            field=models.CharField(default='prefix', max_length=10),
        ),
        migrations.AddField(
            model_name='sellingoffer',
            name='send_color',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sellingoffer',
            name='send_flag',
            field=models.BooleanField(default=False),
        ),
    ]
