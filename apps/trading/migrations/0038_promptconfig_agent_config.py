from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_providers', '0005_update_deepseek_v4_models'),
        ('trading', '0037_noninventoryproduct_noninventoryproductmention_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='promptconfig',
            name='agent_config',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'capability': 'agent'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='prompt_configs',
                to='ai_providers.aiproviderconfig',
            ),
        ),
    ]
