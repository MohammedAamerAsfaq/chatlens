from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0038_promptconfig_agent_config'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiparsinglog',
            name='skip_reason',
            field=models.CharField(blank=True, choices=[('no_text', 'No text content'), ('outbound', 'Outbound message'), ('too_old', 'Older than 24h (history sync)'), ('company_disabled', 'AI parsing off for this company'), ('chat_disabled', 'AI parsing off for this chat'), ('account_disabled', 'AI parsing off for this account'), ('duplicate_broadcast', 'Duplicate of a recent group broadcast')], max_length=30),
        ),
    ]
