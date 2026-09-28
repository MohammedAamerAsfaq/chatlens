'use strict';

const cacheBySocket = new WeakMap();
const CACHE_TTL_MS = Math.max(1000, Number.parseInt(
  process.env.WHATSAPP_PARTICIPATING_GROUP_CACHE_TTL_MS || '300000', 10,
));
const FAILURE_BACKOFF_MS = Math.max(1000, Number.parseInt(
  process.env.WHATSAPP_GROUP_METADATA_BACKOFF_MS || '30000', 10,
));

function stateFor(sock) {
  if (!cacheBySocket.has(sock)) {
    cacheBySocket.set(sock, {
      groups: null, fetchedAt: 0, pending: null, retryAfter: 0, lastError: null,
    });
  }
  return cacheBySocket.get(sock);
}

async function fetchParticipatingGroups(sock, { force = false } = {}) {
  const state = stateFor(sock);
  const now = Date.now();
  if (!force && state.groups && now - state.fetchedAt < CACHE_TTL_MS) return state.groups;
  if (state.pending) return await state.pending;
  if (!force && state.retryAfter > now && state.lastError) throw state.lastError;

  state.pending = (async () => {
    try {
      const groups = await sock.groupFetchAllParticipating();
      state.groups = groups || {};
      state.fetchedAt = Date.now();
      state.retryAfter = 0;
      state.lastError = null;
      return state.groups;
    } catch (error) {
      state.retryAfter = Date.now() + FAILURE_BACKOFF_MS;
      state.lastError = error;
      throw error;
    } finally {
      state.pending = null;
    }
  })();
  return await state.pending;
}

async function fetchGroupMetadata(sock, groupJid) {
  try {
    return await sock.groupMetadata(groupJid);
  } catch (primaryError) {
    try {
      const participating = await fetchParticipatingGroups(sock);
      const metadata = participating?.[groupJid]
        || Object.values(participating || {}).find(group => group?.id === groupJid);
      if (metadata) return metadata;
    } catch (fallbackError) {
      // A fallback rate-limit/outage is more actionable than the direct lookup denial.
      throw fallbackError;
    }
    throw primaryError;
  }
}

module.exports = { fetchGroupMetadata, fetchParticipatingGroups };
