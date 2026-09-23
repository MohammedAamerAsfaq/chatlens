'use strict';

async function fetchGroupMetadata(sock, groupJid) {
  try {
    return await sock.groupMetadata(groupJid);
  } catch (primaryError) {
    try {
      const participating = await sock.groupFetchAllParticipating();
      const metadata = participating?.[groupJid]
        || Object.values(participating || {}).find(group => group?.id === groupJid);
      if (metadata) return metadata;
    } catch {
      // Preserve the specific direct-lookup failure when both lookups fail.
    }
    throw primaryError;
  }
}

module.exports = { fetchGroupMetadata };
