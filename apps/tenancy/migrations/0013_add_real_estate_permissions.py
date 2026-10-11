from django.db import migrations


PERMISSIONS = (
    ('real_estate.board.view', False, False),
    ('real_estate.opportunities.view', True, False),
    ('real_estate.opportunities.update', True, False),
    ('real_estate.properties.view', False, False),
    ('real_estate.properties.manage', False, True),
    ('real_estate.listings.view', False, False),
    ('real_estate.listings.manage', False, True),
    ('real_estate.matches.manage', False, False),
    ('real_estate.settings.manage', False, True),
)


def add_permissions(apps, schema_editor):
    permission_model = apps.get_model('tenancy', 'PermissionDefinition')
    grant_model = apps.get_model('tenancy', 'CompanyRolePermission')
    role_model = apps.get_model('tenancy', 'CompanyRole')

    definitions = {}
    for code, scoped, sensitive in PERMISSIONS:
        area, resource, action = code.split('.', 2)
        definitions[code], _ = permission_model.objects.update_or_create(
            code=code,
            defaults={
                'area': area,
                'label': f'{resource.replace("_", " ").title()}: {action.replace("_", " ").title()}',
                'supports_scope': scoped,
                'is_sensitive': sensitive,
            },
        )

    read_codes = {code for code, _, _ in PERMISSIONS if code.endswith('.view')}
    agent_codes = read_codes | {'real_estate.opportunities.update'}
    for role in role_model.objects.all().iterator():
        if role.key in {'super_user', 'admin', 'manager'}:
            codes = set(definitions)
        elif role.key == 'user':
            codes = agent_codes
        elif role.key == 'viewer':
            codes = read_codes
        else:
            codes = set()
        grant_model.objects.bulk_create([
            grant_model(
                company_id=role.company_id,
                role=role,
                permission=definitions[code],
                record_scope='assigned' if role.key == 'user' and definitions[code].supports_scope else 'all',
            )
            for code in codes
        ], ignore_conflicts=True)


def remove_permissions(apps, schema_editor):
    apps.get_model('tenancy', 'PermissionDefinition').objects.filter(
        code__in=[row[0] for row in PERMISSIONS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0012_usercompanypreference_inspinia_config')]
    operations = [migrations.RunPython(add_permissions, remove_permissions)]
