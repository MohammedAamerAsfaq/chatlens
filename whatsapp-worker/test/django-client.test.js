'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { DjangoClient } = require('../src/django-client');

function makeLogger() {
  return {
    info: test.mock.fn(),
    warn: test.mock.fn(),
    error: test.mock.fn(),
    debug: test.mock.fn(),
  };
}

function makeClient() {
  const logsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'chatlens-django-client-test-'));
  const logger = makeLogger();
  const client = new DjangoClient({
    baseUrl: 'http://django.test',
    token: 'test-token',
    logger,
    logsDir,
  });
  return { client, logger, logsDir };
}

function readFallbackRecords(logsDir) {
  const filePath = path.join(logsDir, 'failed-reports.ndjson');
  return fs.readFileSync(filePath, 'utf8')
    .split(/\r?\n/)
    .filter(Boolean)
    .map(line => JSON.parse(line));
}

test('metadata update failures are written to local fallback reports', async () => {
  const { client, logsDir } = makeClient();
  client.http.post = test.mock.fn(async () => { throw new Error('django unreachable'); });

  await client.sendContactsUpdate('session-1', [{ wa_contact_id: '971500000000@s.whatsapp.net', push_name: 'Buyer' }]);
  await client.sendGroupUpdate('session-1', { group_id: '120363@g.us', name: 'Desk' });
  await client.sendGroupParticipantsUpdate('session-1', '120363@g.us', 'add', ['971500000000@s.whatsapp.net']);

  const records = readFallbackRecords(logsDir);
  assert.deepEqual(records.map(record => record.kind), [
    'contacts_update',
    'group_update',
    'group_participants_update',
  ]);
  assert.equal(records[0].payload.worker_session_id, 'session-1');
  assert.equal(records[1].payload.group_id, '120363@g.us');
  assert.equal(records[2].payload.action, 'add');
});

test('fallback replay posts replay-safe metadata records and removes the file on success', async () => {
  const { client, logsDir } = makeClient();
  const filePath = path.join(logsDir, 'failed-reports.ndjson');
  fs.writeFileSync(filePath, [
    JSON.stringify({ kind: 'contacts_update', payload: { worker_session_id: 'session-1', contacts: [] } }),
    JSON.stringify({ kind: 'group_update', payload: { worker_session_id: 'session-1', group_id: '120363@g.us' } }),
    JSON.stringify({
      kind: 'group_participants_update',
      payload: { worker_session_id: 'session-1', group_id: '120363@g.us', action: 'add', participants: [] },
    }),
  ].join('\n') + '\n', 'utf8');
  client.http.post = test.mock.fn(async () => ({ data: { success: true } }));

  const result = await client.replayFallbackReports();

  assert.deepEqual(result, { attempted: 3, replayed: 3, retained: 0 });
  assert.equal(client.http.post.mock.callCount(), 3);
  assert.equal(fs.existsSync(filePath), false);
});

test('fallback replay retains records that still fail', async () => {
  const { client, logsDir } = makeClient();
  const filePath = path.join(logsDir, 'failed-reports.ndjson');
  fs.writeFileSync(filePath, [
    JSON.stringify({ kind: 'contacts_update', payload: { worker_session_id: 'session-1', contacts: [] } }),
  ].join('\n') + '\n', 'utf8');
  client.http.post = test.mock.fn(async () => { throw new Error('still down'); });

  const result = await client.replayFallbackReports();

  assert.deepEqual(result, { attempted: 1, replayed: 0, retained: 1 });
  const records = readFallbackRecords(logsDir);
  assert.equal(records[0].kind, 'contacts_update');
});
