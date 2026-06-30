from django.db import migrations, models
import django.db.models.deletion


def merge_lid_contacts(apps, schema_editor):
    """
    Merge @lid contact rows into their matching @s.whatsapp.net contact rows.

    Before this migration contacts could have two DB rows for the same person:
      - wa_contact_id = 200506303578143@lid   (created from group messages)
      - wa_contact_id = 971503218002@s.whatsapp.net  (created from direct messages)

    After: one canonical phone-JID row with lid_jid set as alias, all messages
    and chats re-linked to it, and the orphan LID row deleted.

    LID contacts with no phone_number are skipped — they cannot be merged without
    knowing the phone JID and should remain as-is for now (very rare after contacts.set
    populates session.lidToPhone at connect time).
    """
    Contact = apps.get_model('whatsapp_bridge', 'WhatsAppContact')
    Message = apps.get_model('whatsapp_bridge', 'WhatsAppMessage')
    Chat = apps.get_model('whatsapp_bridge', 'WhatsAppChat')

    for lid_contact in list(
        Contact.objects.filter(wa_contact_id__endswith='@lid', phone_number__gt='')
        .select_related('account')
    ):
        phone_jid = f"{lid_contact.phone_number}@s.whatsapp.net"

        phone_contact, created = Contact.objects.get_or_create(
            account=lid_contact.account,
            wa_contact_id=phone_jid,
            defaults={
                'phone_number': lid_contact.phone_number,
                'display_name': lid_contact.display_name,
                'push_name': lid_contact.push_name,
                'lid_jid': lid_contact.wa_contact_id,
            },
        )

        if not created:
            updates = {'lid_jid': lid_contact.wa_contact_id}
            if not phone_contact.push_name and lid_contact.push_name:
                updates['push_name'] = lid_contact.push_name
            if not phone_contact.display_name and lid_contact.display_name:
                updates['display_name'] = lid_contact.display_name
            Contact.objects.filter(pk=phone_contact.pk).update(**updates)
            phone_contact.refresh_from_db()

        # Re-link messages from the LID contact to the canonical phone contact
        Message.objects.filter(
            account=lid_contact.account, contact=lid_contact
        ).update(contact=phone_contact)

        # Re-link and merge individual chats whose wa_chat_id IS the LID JID
        for lid_chat in list(
            Chat.objects.filter(
                account=lid_contact.account, wa_chat_id=lid_contact.wa_contact_id
            )
        ):
            existing_phone_chat = Chat.objects.filter(
                account=lid_contact.account, wa_chat_id=phone_jid
            ).first()

            if existing_phone_chat:
                # Phone-JID chat already exists — fold messages into it and drop the LID chat
                Message.objects.filter(
                    account=lid_contact.account, chat=lid_chat
                ).update(chat=existing_phone_chat)
                lid_chat.delete()
            else:
                # Promote the LID chat to a phone-JID chat in-place
                Chat.objects.filter(pk=lid_chat.pk).update(
                    wa_chat_id=phone_jid,
                    contact=phone_contact,
                )

        # Re-link any remaining chats that reference the LID contact (e.g. contact FK only)
        Chat.objects.filter(
            account=lid_contact.account, contact=lid_contact
        ).update(contact=phone_contact)

        lid_contact.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0007_add_dropped_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappcontact',
            name='lid_jid',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddConstraint(
            model_name='whatsappcontact',
            constraint=models.UniqueConstraint(
                condition=models.Q(lid_jid__isnull=False) & ~models.Q(lid_jid=''),
                fields=['account', 'lid_jid'],
                name='unique_account_lid_jid',
            ),
        ),
        migrations.RunPython(merge_lid_contacts, migrations.RunPython.noop),
    ]
