'use strict';

const DESTINATION = Object.freeze({
  DIRECT: 'direct_contact',
  GROUP: 'standard_group',
  COMMUNITY: 'community',
  COMMUNITY_ANNOUNCEMENT: 'community_announcement',
  COMMUNITY_SUBGROUP: 'community_subgroup',
  CHANNEL: 'channel',
  BROADCAST: 'broadcast',
  STATUS: 'status',
  UNKNOWN: 'unknown',
});

function classifyDestination(jid, metadata = null) {
  const value = String(jid || '').trim().toLowerCase();
  if (value === 'status@broadcast') return DESTINATION.STATUS;
  if (value.endsWith('@newsletter')) return DESTINATION.CHANNEL;
  if (value.endsWith('@broadcast')) return DESTINATION.BROADCAST;
  if (value.endsWith('@g.us')) {
    if (metadata?.isCommunityAnnounce) return DESTINATION.COMMUNITY_ANNOUNCEMENT;
    if (metadata?.isCommunity) return DESTINATION.COMMUNITY;
    if (metadata?.linkedParent) return DESTINATION.COMMUNITY_SUBGROUP;
    return DESTINATION.GROUP;
  }
  if (value.endsWith('@s.whatsapp.net') || value.endsWith('@lid')) return DESTINATION.DIRECT;
  return DESTINATION.UNKNOWN;
}

function normalizedUserJid(jid) {
  const value = String(jid || '').trim().toLowerCase();
  const separator = value.indexOf('@');
  if (separator < 1) return '';
  const user = value.slice(0, separator).split(':')[0];
  const server = value.slice(separator + 1);
  if (!user || !['s.whatsapp.net', 'lid', 'hosted.lid'].includes(server)) return '';
  return `${user}@${server}`;
}

function identityJids(identity) {
  const values = typeof identity === 'string'
    ? [identity]
    : [identity?.id, identity?.jid, identity?.lid, identity?.phoneNumber];
  return new Set(values.map(normalizedUserJid).filter(Boolean));
}

function accountParticipant(metadata, ownIdentity) {
  const ownJids = identityJids(ownIdentity);
  if (!ownJids.size) return null;
  return (metadata?.participants || []).find((participant) => {
    const participantJids = identityJids(participant);
    return [...participantJids].some(candidate => ownJids.has(candidate));
  }) || null;
}

function participantRole(participant) {
  if (participant?.superAdmin || participant?.isSuperAdmin || participant?.admin === 'superadmin') {
    return 'superadmin';
  }
  if (participant?.admin || participant?.isAdmin) return 'admin';
  return participant ? 'member' : '';
}

function normalizeGroupMetadata(metadata, ownIdentity) {
  const participant = accountParticipant(metadata, ownIdentity);
  const role = participantRole(participant);
  const type = classifyDestination(metadata?.id, metadata);
  let canSend = false;
  let blockReason = 'not_a_group_participant';

  if (type === DESTINATION.COMMUNITY) {
    blockReason = 'community_send_blocked';
  } else if (participant && (metadata?.announce || metadata?.isCommunityAnnounce)
      && !['admin', 'superadmin'].includes(role)) {
    blockReason = 'group_admin_required';
  } else if (participant) {
    canSend = true;
    blockReason = '';
  }

  return {
    group_id: metadata.id,
    name: metadata.subject || '',
    description: metadata.desc || '',
    owner_jid: metadata.owner || metadata.ownerJid || '',
    is_community: Boolean(metadata.isCommunity),
    is_community_announcement: Boolean(metadata.isCommunityAnnounce),
    community_id: metadata.linkedParent || null,
    announce: Boolean(metadata.announce),
    restrict: Boolean(metadata.restrict),
    account_is_participant: Boolean(participant),
    account_participant_role: role,
    can_send: canSend,
    send_block_reason: blockReason,
    metadata_complete: true,
    participants: (metadata.participants || []).map(item => ({
      jid: item.id,
      role: participantRole(item),
    })),
  };
}

module.exports = {
  DESTINATION,
  classifyDestination,
  normalizeGroupMetadata,
};
