'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { fetchGroupMetadata } = require('../src/outbound/group-metadata');

test('falls back to participating groups when direct metadata is forbidden', async () => {
  const metadata = { id: '120001@g.us', subject: 'Fallback group' };
  const sock = {
    groupMetadata: test.mock.fn(async () => { throw new Error('forbidden'); }),
    groupFetchAllParticipating: test.mock.fn(async () => ({ [metadata.id]: metadata })),
  };

  const result = await fetchGroupMetadata(sock, metadata.id);

  assert.equal(result, metadata);
  assert.equal(sock.groupFetchAllParticipating.mock.callCount(), 1);
});

test('preserves the direct metadata error when the group is not participating', async () => {
  const primaryError = new Error('forbidden');
  const sock = {
    groupMetadata: async () => { throw primaryError; },
    groupFetchAllParticipating: async () => ({}),
  };

  await assert.rejects(fetchGroupMetadata(sock, '120002@g.us'), error => error === primaryError);
});
