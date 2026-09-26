import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce


def assign_log_companies(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    AgentCallLog = apps.get_model('trading', 'AgentCallLog')
    WhatsAppMessage = apps.get_model('whatsapp_bridge', 'WhatsAppMessage')
    control = Company.objects.filter(company_type='control').order_by('id').first()
    if control is None:
        control = Company.objects.order_by('id').first()
    if control is None:
        return
    message_company = WhatsAppMessage.objects.filter(
        pk=OuterRef('wa_message_id'),
    ).values('account__communication_account__company_id')[:1]
    AgentCallLog.objects.filter(company__isnull=True).update(
        company_id=Coalesce(Subquery(message_company), control.pk),
    )


class Migration(migrations.Migration):
    dependencies = [
        ('tenancy', '0006_company_enforce_validity_period'),
        ('trading', '0056_direct_campaign_chatlens_counters'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentcalllog',
            name='company',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='agent_call_logs',
                to='tenancy.company',
            ),
        ),
        migrations.RunPython(assign_log_companies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='agentcalllog',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='agent_call_logs',
                to='tenancy.company',
            ),
        ),
    ]
