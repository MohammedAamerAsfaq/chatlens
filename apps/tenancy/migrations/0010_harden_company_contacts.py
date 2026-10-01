import re

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def _normalize(identity_type, value):
    raw = str(value or '').strip()
    if identity_type == 'email':
        return raw.casefold()
    if identity_type == 'phone':
        return re.sub(r'\D+', '', raw)
    if identity_type == 'whatsapp_jid':
        jid = raw.casefold()
        return re.sub(r'^([^:@]+):\d+(@.+)$', r'\1\2', jid)
    if identity_type in {'telegram_handle', 'discord_handle'}:
        return raw.lstrip('@').casefold()
    return ' '.join(raw.casefold().split())


def backfill_contact_fields(apps, schema_editor):
    Contact = apps.get_model('tenancy', 'CompanyContact')
    Identity = apps.get_model('tenancy', 'CompanyContactIdentity')
    Contact.objects.filter(is_company=True).update(contact_type='organization')
    now = timezone.now()
    for identity in Identity.objects.select_related('contact').iterator(chunk_size=500):
        identity.company_id = identity.contact.company_id
        identity.normalized_value = _normalize(identity.identity_type, identity.value)
        identity.created_at = identity.created_at or now
        identity.updated_at = identity.updated_at or now
        identity.save(update_fields=[
            'company_id', 'normalized_value', 'created_at', 'updated_at',
        ])


class Migration(migrations.Migration):
    dependencies = [
        ('tenancy', '0009_seed_default_company_roles'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='companycontact', name='contact_type',
            field=models.CharField(
                choices=[('person', 'Person'), ('organization', 'Organization')],
                default='person', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='companycontact', name='first_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='companycontact', name='middle_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='companycontact', name='last_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='companycontact', name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companycontact', name='created_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='company_contacts_created', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='companycontact', name='updated_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='company_contacts_updated', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='company',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='contact_identities', to='tenancy.company',
            ),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='normalized_value',
            field=models.CharField(db_index=True, default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='label',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='source_type',
            field=models.CharField(
                choices=[('manual', 'Manual'), ('whatsapp', 'WhatsApp'),
                         ('integration', 'Integration'), ('import', 'Import')],
                default='manual', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='source_reference',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='companycontactidentity', name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(backfill_contact_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='companycontactidentity', name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='contact_identities', to='tenancy.company',
            ),
        ),
        migrations.AlterField(
            model_name='companycontactidentity', name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='companycontactidentity', name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddIndex(
            model_name='companycontactidentity',
            index=models.Index(
                fields=['company', 'identity_type', 'normalized_value'],
                name='tenant_identity_lookup_idx',
            ),
        ),
    ]
