'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const test = require('node:test');
const assert = require('node:assert/strict');
const { IngestionBuffer, IngestionDispatcher } = require('../src/ingestion-buffer');

function makeBuffer() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'chatlens-ingestion-buffer-'));
  const buffer = new IngestionBuffer({
    databasePath: path.join(directory, 'ingestion.sqlite'),
    logger: { debug() {}, warn() {}, error() {} },
    retryBaseMs: 1,
    retryMaxMs: 1,
  });
  return { buffer, directory };
}

test('Ingestion Buffer persists, deduplicates, and delivers an event', async () => {
  const { buffer, directory } = makeBuffer();
  try {
    const first = buffer.enqueue({ sessionId: '1', providerMessageId: 'message-1', rawPayload: { message: 'hello' } });
    const duplicate = buffer.enqueue({ sessionId: '1', providerMessageId: 'message-1', rawPayload: { message: 'hello' } });
    assert.equal(first.duplicate, false);
    assert.equal(duplicate.duplicate, true);
    const dispatcher = new IngestionDispatcher({
      buffer,
      deliver: async (_event, payload) => ({ success: payload.message === 'hello' }),
      logger: { debug() {}, warn() {}, error() {} },
    });
    await dispatcher.dispatchOnce();
    const row = buffer.db.prepare('SELECT status, attempts FROM ingestion_event WHERE id = ?').get(first.id);
    assert.equal(row.status, 'delivered');
    assert.equal(row.attempts, 1);
  } finally {
    buffer.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('Ingestion Dispatcher retains failed delivery for retry', async () => {
  const { buffer, directory } = makeBuffer();
  try {
    const event = buffer.enqueue({ sessionId: '1', providerMessageId: 'message-2', rawPayload: { message: 'retry' } });
    const dispatcher = new IngestionDispatcher({
      buffer,
      deliver: async () => { throw new Error('Django unavailable'); },
      logger: { debug() {}, warn() {}, error() {} },
    });
    await dispatcher.dispatchOnce();
    const row = buffer.db.prepare('SELECT status, last_error FROM ingestion_event WHERE id = ?').get(event.id);
    assert.equal(row.status, 'pending');
    assert.match(row.last_error, /Django unavailable/);
  } finally {
    buffer.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('raw reception can be persisted before payload normalization', async () => {
  const { buffer, directory } = makeBuffer();
  try {
    const event = buffer.enqueue({
      sessionId: '1', providerMessageId: 'message-3',
      rawPayload: { _pending_normalization: true, raw_baileys_event: { key: { id: 'message-3' } } },
    });
    buffer.replacePayload(event.id, {
      eventType: 'message_ingest', rawJid: '971500000000@s.whatsapp.net',
      rawPayload: { provider_message_id: 'message-3', message_text: 'normalized' },
    });
    const dispatcher = new IngestionDispatcher({
      buffer,
      deliver: async (_event, payload) => ({ success: payload.message_text === 'normalized' }),
      logger: { debug() {}, warn() {}, error() {} },
    });
    await dispatcher.dispatchOnce();
    assert.equal(buffer.db.prepare('SELECT status FROM ingestion_event WHERE id = ?').get(event.id).status, 'delivered');
  } finally {
    buffer.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
