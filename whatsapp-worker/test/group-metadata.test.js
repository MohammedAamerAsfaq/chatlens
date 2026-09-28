'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  fetchGroupMetadata,
  fetchParticipatingGroups,
} = require('../src/outbound/group-metadata');

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

test('reuses one participating-group response across fallback lookups', async () => {
  const first = { id: '120003@g.us', subject: 'First' };
  const second = { id: '120004@g.us', subject: 'Second' };
  const sock = {
    groupMetadata: test.mock.fn(async () => { throw new Error('forbidden'); }),
    groupFetchAllParticipating: test.mock.fn(async () => ({
      [first.id]: first,
      [second.id]: second,
    })),
  };

  assert.equal(await fetchGroupMetadata(sock, first.id), first);
  assert.equal(await fetchGroupMetadata(sock, second.id), second);
  assert.equal(sock.groupFetchAllParticipating.mock.callCount(), 1);
});

test('coalesces concurrent participating-group requests', async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const sock = {
    groupFetchAllParticipating: test.mock.fn(async () => {
      await pending;
      return {};
    }),
  };

  const first = fetchParticipatingGroups(sock);
  const second = fetchParticipatingGroups(sock);
  release();
  await Promise.all([first, second]);
  assert.equal(sock.groupFetchAllParticipating.mock.callCount(), 1);
});

test('reports fallback throttling instead of masking it as forbidden', async () => {
  const rateLimit = new Error('rate-overlimit');
  const sock = {
    groupMetadata: async () => { throw new Error('forbidden'); },
    groupFetchAllParticipating: async () => { throw rateLimit; },
  };

  await assert.rejects(
    fetchGroupMetadata(sock, '120005@g.us'),
    error => error === rateLimit,
  );
});
