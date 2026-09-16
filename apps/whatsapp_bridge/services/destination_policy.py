from datetime import timedelta

from django.conf import settings
from django.utils import timezone


DIRECT_CONTACT = 'direct_contact'
STANDARD_GROUP = 'standard_group'
COMMUNITY = 'community'
COMMUNITY_ANNOUNCEMENT = 'community_announcement'
COMMUNITY_SUBGROUP = 'community_subgroup'
CHANNEL = 'channel'
BROADCAST = 'broadcast'
STATUS = 'status'
UNKNOWN = 'unknown'


def classify_destination(destination_jid, group=None):
    jid = (destination_jid or '').strip().lower()
    if jid == 'status@broadcast':
        return STATUS
    if jid.endswith('@newsletter'):
        return CHANNEL
    if jid.endswith('@broadcast'):
        return BROADCAST
    if jid.endswith('@g.us'):
        if group and group.is_community_announcement:
            return COMMUNITY_ANNOUNCEMENT
        if group and group.is_community:
            return COMMUNITY
        if group and group.community_id:
            return COMMUNITY_SUBGROUP
        return STANDARD_GROUP
    if jid.endswith('@s.whatsapp.net') or jid.endswith('@lid'):
        return DIRECT_CONTACT
    return UNKNOWN


def _metadata_is_fresh(group, checked_at):
    if not group or not group.metadata_refreshed_at:
        return False
    max_age = getattr(settings, 'WHATSAPP_GROUP_METADATA_MAX_AGE_SECONDS', 900)
    return group.metadata_refreshed_at >= checked_at - timedelta(seconds=max_age)


def evaluate_destination(account, destination_jid, group=None, checked_at=None):
    checked_at = checked_at or timezone.now()
    destination_type = classify_destination(destination_jid, group)
    metadata_fresh = _metadata_is_fresh(group, checked_at)
    reason = ''

    if destination_type == COMMUNITY:
        reason = 'community_send_blocked'
    elif destination_type == CHANNEL:
        reason = 'channel_send_blocked'
    elif destination_type in {BROADCAST, STATUS}:
        reason = 'destination_unsupported'
    elif destination_type == UNKNOWN:
        reason = 'destination_unsupported'
    elif destination_type == DIRECT_CONTACT and destination_jid.lower().endswith('@lid'):
        reason = 'recipient_identity_unresolved'
    elif destination_type in {STANDARD_GROUP, COMMUNITY_ANNOUNCEMENT, COMMUNITY_SUBGROUP}:
        if not group:
            reason = 'group_metadata_unavailable'
        elif not metadata_fresh:
            reason = 'group_metadata_stale'
        elif not group.can_send:
            reason = group.send_block_reason or 'group_send_blocked'

    if not reason and not account.outbound_sending_enabled:
        reason = 'master_sending_disabled'
    elif not reason and destination_type == DIRECT_CONTACT and not account.direct_sending_enabled:
        reason = 'direct_sending_disabled'
    elif not reason and destination_type in {
        STANDARD_GROUP,
        COMMUNITY_ANNOUNCEMENT,
        COMMUNITY_SUBGROUP,
    } and not account.group_sending_enabled:
        reason = 'group_sending_disabled'

    return {
        'destination_jid': destination_jid,
        'destination_type': destination_type,
        'allowed': not reason,
        'reason': reason,
        'metadata_fresh': metadata_fresh,
        'metadata_refreshed_at': group.metadata_refreshed_at if group else None,
        'dry_run': True,
    }
