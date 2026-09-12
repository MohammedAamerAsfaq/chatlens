from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('trading', '0045_promptconfig_kiwi_router')]

    operations = [
        migrations.AddField(model_name='aiparsev2log', name='gate_mode', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='aiparsev2log', name='gate_decision', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='aiparsev2log', name='gate_request', field=models.JSONField(blank=True, null=True)),
        migrations.AddField(model_name='aiparsev2log', name='gate_response', field=models.TextField(blank=True)),
        migrations.AddField(model_name='aiparsev2log', name='gate_ai_ms', field=models.PositiveIntegerField(blank=True, null=True)),
    ]
