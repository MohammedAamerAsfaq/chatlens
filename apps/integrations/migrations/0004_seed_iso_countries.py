from pathlib import Path

from django.db import migrations

from apps.integrations.services.geography_sync import normalize_name

COUNTRIES_FILE = Path(__file__).resolve().parent.parent / 'data' / 'iso3166_countries.tsv'


def seed_countries(apps, schema_editor):
    # The full ISO 3166-1 list, so every country can be chosen without a GeoNames sync.
    # Rows a GeoNames sync already created keep their data; only a missing ISO3 is filled in.
    Country = apps.get_model('integrations', 'Country')
    existing = {country.iso2: country for country in Country.objects.all()}
    for line in COUNTRIES_FILE.read_text(encoding='utf-8').splitlines():
        iso2, iso3, name = line.split('\t')
        country = existing.get(iso2)
        if country is None:
            Country.objects.create(iso2=iso2, iso3=iso3, name=name, normalized_name=normalize_name(name))
        elif not country.iso3:
            country.iso3 = iso3
            country.save(update_fields=['iso3'])


class Migration(migrations.Migration):
    dependencies = [('integrations', '0003_integrationconnection_secret_value_and_more')]
    operations = [migrations.RunPython(seed_countries, migrations.RunPython.noop)]
