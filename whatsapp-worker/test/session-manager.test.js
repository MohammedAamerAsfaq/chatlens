'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { SessionManager } = require('../src/session-manager');

const SESSION_ID = 'test-session';

function makeLogger() {
  return {
    info:  test.mock.fn(),
    warn:  test.mock.fn(),
    error: test.mock.fn(),
    debug: test.mock.fn(),
  };
}

function makeDjangoClient(overrides = {}) {
  return {
    lookupLidMapping:    test.mock.fn(async () => ({ found: false })),
    sendUnresolvedMessage: test.mock.fn(async () => ({ success: true, id: 1, resolution_status: 'pending' })),
    sendWorkerAlert:     test.mock.fn(async () => ({ success: true })),
    sendDroppedMessage:  test.mock.fn(async () => ({ success: true })),
    sendBaileysEvent:    test.mock.fn(async () => ({ success: true })),
    sendMessageIngest:   test.mock.fn(async () => ({ success: true })),
    ...overrides,
  };
}

function makeSessionManager({ djangoClient } = {}) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'chatlens-worker-test-'));
  const messageLogger = { write: test.mock.fn(), logsDir: tmpDir };
  const logger = makeLogger();
  const sm = new SessionManager({
    sessionStorePath: tmpDir,
    djangoClient: djangoClient || makeDjangoClient(),
    messageLogger,
    logger,
  });
  const session = {
    sock: {}, // group name / media-download branches are not exercised in these tests
    lidToPhone: {},
    usernameToPhone: {},
    autoDownloadMedia: false,
    knownStuckMessageIds: new Set(),
    consecutiveDecryptFailures: 0,
    consecutiveInitQueryTimeouts: 0,
    connectionUnhealthy: false,
  };
  sm.sessions.set(SESSION_ID, session);
  return { sm, session, logger, messageLogger, djangoClient: sm.djangoClient };
}

let msgCounter = 0;
function makeMsg(overrides = {}) {
  msgCounter += 1;
  return {
    key: { id: `MSG_${msgCounter}`, fromMe: false, remoteJid: '971500000000@s.whatsapp.net', ...(overrides.key || {}) },
    message: { conversation: 'hello' },
    messageTimestamp: 1700000000 + msgCounter,
    pushName: 'Tester',
    ...Object.fromEntries(Object.entries(overrides).filter(([k]) => k !== 'key')),
  };
}

// --- A. Existing inbound phone JID ---------------------------------------
test('A. inbound phone-JID message ingests normally, no unresolved record', async () => {
  const { sm, djangoClient } = makeSessionManager();
  const msg = makeMsg({ key: { fromMe: false, remoteJid: '971500000000@s.whatsapp.net' } });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.ok(built, 'expected a built payload');
  assert.equal(built.payload.chat_id, '971500000000@s.whatsapp.net');
  assert.equal(built.payload.direction, 'inbound');
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 0);
  assert.equal(djangoClient.lookupLidMapping.mock.callCount(), 0);
});

// --- B. Existing outbound phone JID --------------------------------------
test('B. outbound phone-JID message ingests normally', async () => {
  const { sm, djangoClient } = makeSessionManager();
  const msg = makeMsg({ key: { fromMe: true, remoteJid: '971500000000@s.whatsapp.net' } });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.ok(built);
  assert.equal(built.payload.direction, 'outbound');
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 0);
});

// --- C. Inbound LID with senderPn ----------------------------------------
test('C. inbound LID with senderPn resolves via source 1 and caches the mapping', async () => {
  const { sm, session, djangoClient } = makeSessionManager();
  const msg = makeMsg({
    key: {
      fromMe: false,
      remoteJid: '16011805913098@lid',
      senderPn: '971544732206@s.whatsapp.net',
    },
  });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.ok(built);
  assert.equal(built.payload.chat_id, '971544732206@s.whatsapp.net');
  assert.equal(session.lidToPhone['16011805913098@lid'], '971544732206@s.whatsapp.net');
  assert.equal(djangoClient.lookupLidMapping.mock.callCount(), 0);
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 0);
});

// --- D. Group LID participant with participantPn -------------------------
test('D. group message from an unresolvable-cache LID participant resolves via participantPn', async () => {
  const { sm, session } = makeSessionManager();
  const msg = makeMsg({
    key: {
      fromMe: false,
      remoteJid: '120363000000000000@g.us',
      participant: '43190593786026@lid',
      participantPn: '971521962376@s.whatsapp.net',
    },
  });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.ok(built);
  assert.equal(built.payload.chat_type, 'group');
  assert.equal(built.payload.sender_number, '971521962376');
  assert.equal(session.lidToPhone['43190593786026@lid'], '971521962376@s.whatsapp.net');
});

// --- E. Outbound LID — memory cache hit -----------------------------------
test('E. outbound LID resolves from a warm in-memory cache without a Django lookup', async () => {
  const { sm, djangoClient, session } = makeSessionManager();
  session.lidToPhone['16011805913098@lid'] = '971544732206@s.whatsapp.net';
  const msg = makeMsg({ key: { fromMe: true, remoteJid: '16011805913098@lid' } });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.ok(built);
  assert.equal(built.payload.chat_id, '971544732206@s.whatsapp.net');
  assert.equal(djangoClient.lookupLidMapping.mock.callCount(), 0);
});

// --- F. Outbound LID — cache miss, persisted Django mapping hit ----------
test('F. outbound LID with a cold cache resolves via the persisted Django mapping (source 3)', async () => {
  const djangoClient = makeDjangoClient({
    lookupLidMapping: test.mock.fn(async () => ({
      found: true, lid_jid: '16011805913098@lid', phone_jid: '971544732206@s.whatsapp.net',
    })),
  });
  const { sm, session } = makeSessionManager({ djangoClient });
  const msg = makeMsg({ key: { fromMe: true, remoteJid: '16011805913098@lid' } });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.ok(built, 'message must be ingested normally, not preserved as unresolved');
  assert.equal(built.payload.chat_id, '971544732206@s.whatsapp.net');
  assert.equal(djangoClient.lookupLidMapping.mock.callCount(), 1);
  assert.equal(session.lidToPhone['16011805913098@lid'], '971544732206@s.whatsapp.net');
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 0);
});

// --- G. Outbound LID — no mapping anywhere --------------------------------
test('G. outbound LID with no mapping anywhere is preserved unresolved, not dropped', async () => {
  const djangoClient = makeDjangoClient({
    lookupLidMapping: test.mock.fn(async () => ({ found: false })),
  });
  const { sm } = makeSessionManager({ djangoClient });
  const msg = makeMsg({
    key: { fromMe: true, remoteJid: '16011805913098@lid', id: 'MSG_G' },
    message: { conversation: '5100' },
  });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.equal(built, null, 'must not be dropped as a normal payload — must return null via preserve path');
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 1);
  const [, sentPayload] = djangoClient.sendUnresolvedMessage.mock.calls[0].arguments;
  assert.equal(sentPayload.reason, 'unresolvable_lid');
  assert.equal(sentPayload.message_text, '5100');
  assert.equal(sentPayload.provider_message_id, 'MSG_G');
  assert.equal(sentPayload.lid_jid, '16011805913098@lid');
  assert.ok(sentPayload.raw_payload, 'full recoverable payload must be included, not just the key');
  assert.equal(djangoClient.sendDroppedMessage.mock.callCount(), 0, 'must not duplicate into DroppedMessage');
});

// --- J. Django persistent-mapping lookup failure --------------------------
test('J. a lookupLidMapping failure preserves the message unresolved instead of guessing', async () => {
  const djangoClient = makeDjangoClient({
    lookupLidMapping: test.mock.fn(async () => { throw new Error('timeout'); }),
  });
  const { sm, logger, session } = makeSessionManager({ djangoClient });
  const msg = makeMsg({ key: { fromMe: true, remoteJid: '16011805913098@lid' } });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.equal(built, null);
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 1);
  assert.equal(session.lidToPhone['16011805913098@lid'], undefined, 'must not cache a guessed/partial mapping');
  assert.ok(
    logger.warn.mock.calls.some(c => /lookupLidMapping failed/.test(c.arguments[1] || '')),
    'the lookup failure itself must be logged, not swallowed',
  );
});

// --- K. unresolved-message persistence failure ----------------------------
test('K. a sendUnresolvedMessage failure raises a WorkerAlert, not a silent success', async () => {
  const djangoClient = makeDjangoClient({
    lookupLidMapping: test.mock.fn(async () => ({ found: false })),
    sendUnresolvedMessage: test.mock.fn(async () => { throw new Error('django unreachable'); }),
  });
  const { sm, logger } = makeSessionManager({ djangoClient });
  const msg = makeMsg({ key: { fromMe: true, remoteJid: '16011805913098@lid' } });

  const built = await sm._buildPayload(SESSION_ID, msg);

  assert.equal(built, null);
  assert.equal(djangoClient.sendWorkerAlert.mock.callCount(), 1);
  const [, alertPayload] = djangoClient.sendWorkerAlert.mock.calls[0].arguments;
  assert.equal(alertPayload.alert_type, 'unresolved_message_failed');
  assert.ok(
    logger.error.mock.calls.some(c => /Failed to preserve unresolved message/.test(c.arguments[1] || '')),
  );
});

// --- L. malformed / unexpected _buildPayload failure is explicitly recorded ---
test('L. an unexpected _buildPayload failure is caught and recorded, never silently dropped', async () => {
  const { sm, djangoClient } = makeSessionManager();
  sm._buildPayload = test.mock.fn(async () => { throw new Error('jidNormalizedUser exploded'); });
  const msg = makeMsg({ key: { id: 'MSG_L' } });

  await sm._forwardMessage(SESSION_ID, msg);

  assert.equal(djangoClient.sendDroppedMessage.mock.callCount(), 1);
  const [, dropped] = djangoClient.sendDroppedMessage.mock.calls[0].arguments;
  assert.equal(dropped.reason, 'build_error');
  assert.equal(dropped.msg_id, 'MSG_L');
});

// --- M. history-sync unresolved LID preserves original timestamp/source ------
test('M. an unresolvable history-sync LID message is preserved unresolved with is_history set', async () => {
  const djangoClient = makeDjangoClient({
    lookupLidMapping: test.mock.fn(async () => ({ found: false })),
  });
  const { sm } = makeSessionManager({ djangoClient });
  const originalTs = 1700000123;
  const msg = makeMsg({
    key: { fromMe: true, remoteJid: '16011805913098@lid', id: 'MSG_M' },
    message: { conversation: 'old stock list' },
    messageTimestamp: originalTs,
  });

  const built = await sm._buildPayload(SESSION_ID, msg, { isHistory: true });

  assert.equal(built, null);
  assert.equal(djangoClient.sendUnresolvedMessage.mock.callCount(), 1);
  const [, sentPayload] = djangoClient.sendUnresolvedMessage.mock.calls[0].arguments;
  assert.equal(sentPayload.is_history, true);
  assert.equal(sentPayload.raw_payload.is_history, true);
  assert.equal(sentPayload.message_time, new Date(originalTs * 1000).toISOString());
});
