from django.db import migrations

CODE = 'conversations.accounts.toggle_ai'


def remove_permission(apps, schema_editor):
    apps.get_model('tenancy', 'PermissionDefinition').objects.filter(code=CODE).delete()


def add_permission(apps, schema_editor):
    permission_model = apps.get_model('tenancy', 'PermissionDefinition')
    permission_model.objects.update_or_create(
        code=CODE,
        defaults={
            'area': 'conversations',
            'label': 'Accounts: Toggle Ai',
            'supports_scope': True,
            'is_sensitive': False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0015_add_toggle_ai_permission')]
    operations = [migrations.RunPython(remove_permission, add_permission)]
