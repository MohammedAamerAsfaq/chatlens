from django.db import migrations


LEGACY_MODEL_MAP = {
    'deepseek-chat': 'deepseek-v4-flash',
    'deepseek-reasoner': 'deepseek-v4-flash',
}


def update_deepseek_models(apps, schema_editor):
    AIProviderConfig = apps.get_model('ai_providers', 'AIProviderConfig')
    for old_model, new_model in LEGACY_MODEL_MAP.items():
        AIProviderConfig.objects.filter(provider='deepseek', model=old_model).update(model=new_model)


class Migration(migrations.Migration):

    dependencies = [
        ('ai_providers', '0004_aiproviderrequestlog'),
    ]

    operations = [
        migrations.RunPython(update_deepseek_models, migrations.RunPython.noop),
    ]
