'use strict';

function isoDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function normalizeCap(data = {}) {
  return {
    total_quota: data.total_quota ?? null,
    used_quota: data.used_quota ?? null,
    cycle_start_timestamp: data.cycle_start_timestamp ?? null,
    cycle_end_timestamp: data.cycle_end_timestamp ?? null,
    server_sent_timestamp: data.server_sent_timestamp ?? null,
    ote_status: data.ote_status || '',
    mv_status: data.mv_status || '',
    capping_status: data.capping_status || '',
  };
}

function normalizeReachout(data = {}) {
  return {
    is_active: Boolean(data.isActive),
    time_enforcement_ends: isoDate(data.timeEnforcementEnds),
    enforcement_type: data.enforcementType || '',
  };
}

function errorMessage(error) {
  return String(error?.message || error || 'Unknown telemetry error').slice(0, 1000);
}

async function withTimeout(operation, timeoutMs, label) {
  let timer;
  try {
    return await Promise.race([
      operation(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function fetchSection(sock, methodName, normalizer, timeoutMs) {
  const checkedAt = new Date().toISOString();
  if (typeof sock?.[methodName] !== 'function') {
    return { status: 'unsupported', checked_at: checkedAt, error: `${methodName} is unavailable` };
  }
  try {
    const data = await withTimeout(() => sock[methodName](), timeoutMs, methodName);
    return { status: 'available', checked_at: checkedAt, data: normalizer(data) };
  } catch (error) {
    return { status: 'unavailable', checked_at: checkedAt, error: errorMessage(error) };
  }
}

async function fetchCapacityTelemetry(sock, timeoutMs = 15000) {
  const [cap, reachout] = await Promise.all([
    fetchSection(sock, 'fetchNewChatMessageCap', normalizeCap, timeoutMs),
    fetchSection(sock, 'fetchAccountReachoutTimelock', normalizeReachout, timeoutMs),
  ]);
  return { source: 'baileys_v7', cap, reachout };
}

function capEvent(data) {
  return {
    source: 'baileys_v7',
    cap: {
      status: 'available',
      checked_at: new Date().toISOString(),
      data: normalizeCap(data),
    },
  };
}

function reachoutEvent(data) {
  return {
    source: 'baileys_v7',
    reachout: {
      status: 'available',
      checked_at: new Date().toISOString(),
      data: normalizeReachout(data),
    },
  };
}

module.exports = {
  capEvent,
  fetchCapacityTelemetry,
  normalizeCap,
  normalizeReachout,
  reachoutEvent,
};
