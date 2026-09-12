from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('trading', '0048_alter_agentcalllog_purpose')]

    operations = [
        migrations.AlterField(
            model_name='aiparsev2log',
            name='gate_mode',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='aiparsev2log',
            name='gate_decision',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='aiparsev2log',
            name='gate_response',
            field=models.TextField(blank=True, null=True),
        ),
    ]
