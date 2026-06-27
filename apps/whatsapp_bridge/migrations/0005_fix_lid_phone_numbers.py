from django.db import migrations


def fix_lid_phone_numbers(apps, schema_editor):
    """
    Contacts with @lid JIDs had their phone_number incorrectly set to the
    LID local part (e.g. '18806883308705' from '18806883308705@lid').
    LIDs are opaque privacy identifiers, not real phone numbers — clear them.
    """
    WhatsAppContact = apps.get_model('whatsapp_bridge', 'WhatsAppContact')
    to_fix = []
    for contact in WhatsAppContact.objects.filter(
        wa_contact_id__endswith='@lid'
    ).exclude(phone_number=''):
        lid_local = contact.wa_contact_id.split('@')[0]
        if contact.phone_number == lid_local:
            contact.phone_number = ''
            to_fix.append(contact)
    if to_fix:
        WhatsAppContact.objects.bulk_update(to_fix, ['phone_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0004_alter_whatsappmessage_media_url'),
    ]

    operations = [
        migrations.RunPython(fix_lid_phone_numbers, migrations.RunPython.noop),
    ]
