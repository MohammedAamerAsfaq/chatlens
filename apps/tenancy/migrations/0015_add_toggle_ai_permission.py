from django.db import migrations

CODE = 'conversations.accounts.toggle_ai'


def add_permission(apps, schema_editor):
    permission_model = apps.get_model('tenancy', 'PermissionDefinition')
    grant_model = apps.get_model('tenancy', 'CompanyRolePermission')
    role_model = apps.get_model('tenancy', 'CompanyRole')

    area, resource, action = CODE.split('.', 2)
    definition, _ = permission_model.objects.update_or_create(
        code=CODE,
        defaults={
            'area': area,
            'label': f'{resource.replace("_", " ").title()}: {action.replace("_", " ").title()}',
            'supports_scope': True,
            'is_sensitive': False,
        },
    )

    for role in role_model.objects.all().iterator():
        if role.key in {'super_user', 'admin', 'manager', 'user'}:
            grant_model.objects.update_or_create(
                company_id=role.company_id,
                role=role,
                permission=definition,
                defaults={'record_scope': 'assigned' if role.key == 'user' else 'all'},
            )


def remove_permission(apps, schema_editor):
    apps.get_model('tenancy', 'PermissionDefinition').objects.filter(code=CODE).delete()


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0014_communication_account_assignments')]
    operations = [migrations.RunPython(add_permission, remove_permission)]
