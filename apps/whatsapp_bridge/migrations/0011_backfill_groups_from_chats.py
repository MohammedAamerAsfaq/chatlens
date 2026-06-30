"""
Data migration: seed WhatsAppGroup placeholder rows from existing WhatsAppChat rows
where chat_type='group'. These rows will be enriched with real metadata (description,
owner, participants, is_community flag) the next time the WhatsApp session connects and
groupFetchAllParticipating() fires.
"""
from django.db import migrations


def backfill_groups(apps, schema_editor):
    WhatsAppChat  = apps.get_model('whatsapp_bridge', 'WhatsAppChat')
    WhatsAppGroup = apps.get_model('whatsapp_bridge', 'WhatsAppGroup')

    group_chats = WhatsAppChat.objects.filter(chat_type='group')
    created = 0
    for chat in group_chats:
        group, was_created = WhatsAppGroup.objects.get_or_create(
            account_id=chat.account_id,
            wa_group_id=chat.wa_chat_id,
            defaults={
                'chat': chat,
                'name': chat.name or '',
            },
        )
        # Link the chat even if the group row already existed but had no chat FK
        if not was_created and group.chat_id is None:
            group.chat = chat
            group.save(update_fields=['chat'])
        if was_created:
            created += 1

    print(f'\n  Backfilled {created} WhatsAppGroup rows from existing group chats '
          f'({group_chats.count()} group chats total).')


def reverse_backfill(apps, schema_editor):
    # Nothing to undo — don't delete rows that may have been enriched by the worker
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0010_add_groups'),
    ]

    operations = [
        migrations.RunPython(backfill_groups, reverse_backfill),
    ]
