from django.db import migrations, models
import django.db.models.deletion


def link_countries(apps, schema_editor):
    # Move any typed country onto the country master; refuse to drop one that matches nothing.
    ClientProfile = apps.get_model('clientpulse', 'ClientProfile')
    Country = apps.get_model('integrations', 'Country')
    unmatched = []
    for profile in ClientProfile.objects.exclude(country_text=''):
        text = profile.country_text.strip()
        country = (
            Country.objects.filter(iso2__iexact=text).first()
            or Country.objects.filter(iso3__iexact=text).first()
            or Country.objects.filter(name__iexact=text).first()
        )
        if country is None:
            unmatched.append(f'{profile.pk}: {text!r}')
            continue
        profile.country = country
        profile.save(update_fields=['country'])
    if unmatched:
        raise RuntimeError('Client countries not in the country master: ' + ', '.join(unmatched))


class Migration(migrations.Migration):
    dependencies = [
        ('clientpulse', '0011_reminder_phrases'),
        ('integrations', '0004_seed_iso_countries'),
    ]
    operations = [
        migrations.RenameField('clientprofile', 'country', 'country_text'),
        migrations.AddField(
            model_name='clientprofile', name='country',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='client_profiles', to='integrations.country',
            ),
        ),
        migrations.RunPython(link_countries, migrations.RunPython.noop),
        migrations.RemoveField('clientprofile', 'country_text'),
    ]
