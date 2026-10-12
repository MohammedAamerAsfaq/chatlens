import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


DEFAULT_TYPES = (
    ('apartment', 'Apartment', 'residential'),
    ('villa', 'Villa', 'residential'),
    ('townhouse', 'Townhouse', 'residential'),
    ('penthouse', 'Penthouse', 'residential'),
    ('duplex', 'Duplex', 'residential'),
    ('studio', 'Studio', 'residential'),
    ('room', 'Room', 'residential'),
    ('office', 'Office', 'commercial'),
    ('retail', 'Retail', 'commercial'),
    ('warehouse', 'Warehouse', 'commercial'),
    ('building', 'Building', 'commercial'),
    ('land', 'Land', 'land'),
    ('other', 'Other', 'other'),
)
AREA_UNITS = [
    ('sqft', 'Square feet'), ('sqm', 'Square metres'), ('sqyd', 'Square yards'),
    ('acre', 'Acres'), ('hectare', 'Hectares'),
]


def seed_and_link_types(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    Property = apps.get_model('real_estate', 'Property')
    Candidate = apps.get_model('real_estate', 'PropertyCandidate')
    PropertyType = apps.get_model('real_estate', 'PropertyType')
    company_ids = set(Company.objects.filter(industry_type='real_estate').values_list('id', flat=True))
    company_ids.update(Company.objects.filter(company_type='control').values_list('id', flat=True))
    company_ids.update(Property.objects.values_list('company_id', flat=True))
    company_ids.update(Candidate.objects.values_list('company_id', flat=True))
    defaults = {code: (name, category) for code, name, category in DEFAULT_TYPES}

    for company_id in company_ids:
        codes = set(Property.objects.filter(company_id=company_id).values_list('property_type_legacy', flat=True))
        codes.update(Candidate.objects.filter(company_id=company_id).values_list('property_type_legacy', flat=True))
        codes.discard('')
        codes.update(defaults)
        records = {}
        for order, code in enumerate(sorted(codes), start=1):
            name, category = defaults.get(code, (code.replace('_', ' ').title(), 'other'))
            record, _ = PropertyType.objects.get_or_create(
                company_id=company_id,
                code=code,
                defaults={'name': name, 'category': category, 'sort_order': order * 10},
            )
            records[code] = record.pk
        for code, type_id in records.items():
            Property.objects.filter(company_id=company_id, property_type_legacy=code).update(property_type_id=type_id)
            Candidate.objects.filter(company_id=company_id, property_type_legacy=code).update(property_type_id=type_id)


class Migration(migrations.Migration):
    dependencies = [('real_estate', '0005_candidateembedding_listingembedding_and_more')]

    operations = [
        migrations.CreateModel(
            name='PropertyType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(max_length=50, validators=[django.core.validators.RegexValidator('^[a-z0-9]+(?:_[a-z0-9]+)*$', 'Use lowercase letters, numbers, and underscores.')])),
                ('category', models.CharField(choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('land', 'Land'), ('other', 'Other')], default='other', max_length=20)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='real_estate_property_types', to='tenancy.company')),
            ],
            options={'db_table': 'real_estate_property_type', 'ordering': ['sort_order', 'name', 'id']},
        ),
        migrations.AddConstraint(model_name='propertytype', constraint=models.UniqueConstraint(fields=('company', 'code'), name='re_property_type_company_code_uniq')),
        migrations.AddConstraint(model_name='propertytype', constraint=models.UniqueConstraint(fields=('company', 'name'), name='re_property_type_company_name_uniq')),
        migrations.RemoveIndex(model_name='property', name='real_estate_company_8373fc_idx'),
        migrations.RenameField(model_name='property', old_name='property_type', new_name='property_type_legacy'),
        migrations.RenameField(model_name='propertycandidate', old_name='property_type', new_name='property_type_legacy'),
        migrations.AddField(model_name='property', name='property_type', field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='properties', to='real_estate.propertytype')),
        migrations.AddField(model_name='propertycandidate', name='property_type', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='candidates', to='real_estate.propertytype')),
        migrations.RunPython(seed_and_link_types, migrations.RunPython.noop),
        migrations.AlterField(model_name='property', name='property_type', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='properties', to='real_estate.propertytype')),
        migrations.RemoveField(model_name='property', name='property_type_legacy'),
        migrations.RemoveField(model_name='propertycandidate', name='property_type_legacy'),
        migrations.AddIndex(model_name='property', index=models.Index(fields=['company', 'property_type', 'availability_status'], name='re_property_type_status_idx')),
        migrations.AlterField(model_name='property', name='area_unit', field=models.CharField(choices=AREA_UNITS, default='sqft', max_length=10)),
        migrations.AlterField(model_name='propertycandidate', name='area_unit', field=models.CharField(choices=AREA_UNITS, default='sqft', max_length=10)),
        migrations.AlterField(model_name='propertyrequirement', name='area_unit', field=models.CharField(choices=AREA_UNITS, default='sqft', max_length=10)),
        migrations.AlterField(model_name='realestatesettings', name='default_area_unit', field=models.CharField(choices=AREA_UNITS, default='sqft', max_length=10)),
    ]
