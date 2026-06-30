from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add username alias column to WhatsAppContact.

    WhatsApp is rolling out usernames (Wave 1: July 7 2026, global: September 2026).
    Like lid_jid, username is a privacy alias — wa_contact_id stays as the canonical
    phone JID. The username is populated from contacts.set when Baileys exposes c.username.

    Max length 35 matches WhatsApp's own username length cap.
    Unique per account (NULLs excluded) so two contacts cannot share a username.
    """

    dependencies = [
        ('whatsapp_bridge', '0008_add_lid_jid_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappcontact',
            name='username',
            field=models.CharField(blank=True, max_length=35, null=True),
        ),
        migrations.AddConstraint(
            model_name='whatsappcontact',
            constraint=models.UniqueConstraint(
                condition=models.Q(username__isnull=False) & ~models.Q(username=''),
                fields=['account', 'username'],
                name='unique_account_username',
            ),
        ),
    ]
