'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  capEvent,
  fetchCapacityTelemetry,
  normalizeReachout,
  reachoutEvent,
} = require('../src/outbound/capacity-telemetry');

test('fetches and normalizes independent cap and reachout telemetry', async () => {
  const sock = {
    fetchNewChatMessageCap: test.mock.fn(async () => ({
      total_quota: 20,
      used_quota: 7,
      capping_status: 'FIRST_WARNING',
    })),
    fetchAccountReachoutTimelock: test.mock.fn(async () => ({
      isActive: true,
      timeEnforcementEnds: new Date('2026-09-16T12:00:00Z'),
      enforcementType: 'BIZ_QUALITY',
    })),
  };

  const result = await fetchCapacityTelemetry(sock, 1000);

  assert.equal(result.cap.status, 'available');
  assert.equal(result.cap.data.total_quota, 20);
  assert.equal(result.reachout.status, 'available');
  assert.equal(result.reachout.data.is_active, true);
  assert.equal(result.reachout.data.time_enforcement_ends, '2026-09-16T12:00:00.000Z');
});

test('one provider failure does not discard the other telemetry section', async () => {
  const sock = {
    fetchNewChatMessageCap: test.mock.fn(async () => { throw new Error('server returned 500'); }),
    fetchAccountReachoutTimelock: test.mock.fn(async () => ({ isActive: false })),
  };

  const result = await fetchCapacityTelemetry(sock, 1000);

  assert.equal(result.cap.status, 'unavailable');
  assert.match(result.cap.error, /500/);
  assert.equal(result.reachout.status, 'available');
  assert.equal(result.reachout.data.is_active, false);
});

test('marks missing Baileys telemetry methods unsupported', async () => {
  const result = await fetchCapacityTelemetry({}, 1000);

  assert.equal(result.cap.status, 'unsupported');
  assert.equal(result.reachout.status, 'unsupported');
});

test('normalizes live cap and reachout events', () => {
  assert.equal(capEvent({ used_quota: 3 }).cap.data.used_quota, 3);
  assert.equal(reachoutEvent({ isActive: true }).reachout.data.is_active, true);
  assert.deepEqual(normalizeReachout({ isActive: false }), {
    is_active: false,
    time_enforcement_ends: null,
    enforcement_type: '',
  });
});
