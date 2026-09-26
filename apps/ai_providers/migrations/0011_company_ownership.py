import django.db.models.deletion
from django.db import migrations, models


def assign_control_company(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    Provider = apps.get_model('ai_providers', 'AIProviderConfig')
    Router = apps.get_model('ai_providers', 'KiwiRouter')
    Target = apps.get_model('ai_providers', 'DefaultAgentTarget')
    control = Company.objects.filter(company_type='control').order_by('id').first()
    if control is None:
        control = Company.objects.order_by('id').first()
    if control is None:
        return
    Provider.objects.filter(company__isnull=True).update(company=control)
    Router.objects.filter(company__isnull=True).update(company=control)
    Target.objects.filter(company__isnull=True).update(company=control)


class Migration(migrations.Migration):
    dependencies = [
        ('tenancy', '0006_company_enforce_validity_period'),
        ('ai_providers', '0010_default_agent_target'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiproviderconfig',
            name='company',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ai_provider_configs',
                to='tenancy.company',
            ),
        ),
        migrations.AddField(
            model_name='kiwirouter',
            name='company',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='kiwi_routers',
                to='tenancy.company',
            ),
        ),
        migrations.AddField(
            model_name='defaultagenttarget',
            name='company',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='default_agent_target',
                to='tenancy.company',
            ),
        ),
        migrations.RunPython(assign_control_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='aiproviderconfig',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ai_provider_configs',
                to='tenancy.company',
            ),
        ),
        migrations.AlterField(
            model_name='kiwirouter',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='kiwi_routers',
                to='tenancy.company',
            ),
        ),
        migrations.AlterField(
            model_name='defaultagenttarget',
            name='company',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='default_agent_target',
                to='tenancy.company',
            ),
        ),
        migrations.AlterField(
            model_name='kiwirouter',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AddConstraint(
            model_name='aiproviderconfig',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)),
                fields=('company', 'capability'),
                name='unique_active_ai_provider_per_company_capability',
            ),
        ),
        migrations.AddConstraint(
            model_name='kiwirouter',
            constraint=models.UniqueConstraint(
                fields=('company', 'name'),
                name='unique_kiwi_router_name_per_company',
            ),
        ),
    ]
