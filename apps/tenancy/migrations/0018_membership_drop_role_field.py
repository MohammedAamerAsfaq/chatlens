"""Drop CompanyMembership.role: access now comes only from assigned roles.

Until now a membership with no role assignments got its permissions from this field.
Before the column goes, any such membership is given the company role with the same
key, so nobody silently loses access. If that role does not exist the migration stops.
"""

from django.db import migrations


def assign_roles_from_field(apps, schema_editor):
    CompanyMembership = apps.get_model('tenancy', 'CompanyMembership')
    CompanyRole = apps.get_model('tenancy', 'CompanyRole')
    MembershipRoleAssignment = apps.get_model('tenancy', 'MembershipRoleAssignment')
    for membership in CompanyMembership.objects.filter(role_assignments__isnull=True):
        role = CompanyRole.objects.filter(company_id=membership.company_id, key=membership.role).first()
        if role is None:
            raise RuntimeError(
                f'Membership {membership.pk} (company {membership.company_id}) has no roles and its '
                f'company has no role {membership.role!r}; assign it a role before migrating.'
            )
        MembershipRoleAssignment.objects.create(
            company_id=membership.company_id, membership=membership, role=role, source='legacy',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0017_membership_removed'),
    ]

    operations = [
        migrations.RunPython(assign_roles_from_field, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='companymembership',
            name='role',
        ),
    ]
