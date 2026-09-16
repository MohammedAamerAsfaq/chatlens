from django.db import transaction
from django.utils import timezone

from apps.whatsapp_bridge.models import (
    ParticipantRole,
    WhatsAppChat,
    WhatsAppContact,
    WhatsAppGroup,
    WhatsAppGroupParticipant,
)


def _as_bool(value):
    return value is True or str(value).lower() in {'1', 'true', 'yes'}


def calculate_group_send_permission(*, is_community, is_community_announcement,
                                    announce, account_is_participant, account_role):
    if is_community and not is_community_announcement:
        return False, 'community_send_blocked'
    if not account_is_participant:
        return False, 'not_a_group_participant'
    if (is_community_announcement or announce) and account_role not in {
        ParticipantRole.ADMIN,
        ParticipantRole.SUPERADMIN,
    }:
        return False, 'group_admin_required'
    return True, ''


def _participant_contact(account, jid):
    if not jid.endswith('@s.whatsapp.net'):
        return None
    return WhatsAppContact.objects.filter(account=account, wa_contact_id=jid).first()


def _sync_participants(account, group, participants):
    active_jids = set()
    for participant in participants:
        jid = (participant.get('jid') or '').strip()
        if not jid:
            continue
        role = participant.get('role') or ParticipantRole.MEMBER
        if role not in ParticipantRole.values:
            role = ParticipantRole.MEMBER
        active_jids.add(jid)
        WhatsAppGroupParticipant.objects.update_or_create(
            group=group,
            wa_jid=jid,
            defaults={
                'role': role,
                'is_active': True,
                'contact': _participant_contact(account, jid),
            },
        )
    WhatsAppGroupParticipant.objects.filter(group=group, is_active=True).exclude(
        wa_jid__in=active_jids,
    ).update(is_active=False)
    group.participant_count = len(active_jids)


@transaction.atomic
def upsert_group_metadata(account, payload):
    group_id = (payload.get('group_id') or '').strip()
    if not group_id.endswith('@g.us'):
        raise ValueError(f'Invalid group JID: {group_id!r}')

    group, _ = WhatsAppGroup.objects.select_for_update().get_or_create(
        account=account,
        wa_group_id=group_id,
    )
    scalar_fields = {
        'name': lambda value: (value or '').strip(),
        'description': lambda value: (value or '').strip(),
        'owner_jid': lambda value: (value or '').strip(),
        'is_community': _as_bool,
        'is_community_announcement': _as_bool,
        'announce': _as_bool,
        'restrict': _as_bool,
        'account_is_participant': _as_bool,
    }
    for field, converter in scalar_fields.items():
        if field in payload:
            setattr(group, field, converter(payload[field]))

    if 'account_participant_role' in payload:
        role = payload.get('account_participant_role') or ''
        group.account_participant_role = role if role in ParticipantRole.values else ''

    if 'community_id' in payload:
        community_id = (payload.get('community_id') or '').strip()
        group.community = None
        if community_id:
            group.community, _ = WhatsAppGroup.objects.get_or_create(
                account=account,
                wa_group_id=community_id,
                defaults={'is_community': True},
            )

    chat = WhatsAppChat.objects.filter(account=account, wa_chat_id=group_id).first()
    if chat:
        group.chat = chat

    if 'participants' in payload:
        _sync_participants(account, group, payload.get('participants') or [])

    if _as_bool(payload.get('metadata_complete')):
        group.can_send, group.send_block_reason = calculate_group_send_permission(
            is_community=group.is_community,
            is_community_announcement=group.is_community_announcement,
            announce=group.announce,
            account_is_participant=group.account_is_participant,
            account_role=group.account_participant_role,
        )
        group.metadata_refreshed_at = timezone.now()

    group.save()
    return group
