'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { OutboundMessageSender } = require('../src/outbound/message-sender');

function request(overrides = {}) {
  return {
    provider_message_id: 'outbound-1',
    destination_jid: '971500000001@s.whatsapp.net',
    content: { text: 'Hello' },
    settings: { account_interval_ms: 1000, recipient_interval_ms: 1000 },
    ...overrides,
  };
}

test('sender validates registration, sends text, and suppresses duplicate provider ids', async () => {
  const sock = {
    onWhatsApp: test.mock.fn(async () => [{ exists: true }]),
    sendMessage: test.mock.fn(async () => ({ key: { id: 'provider-result' } })),
  };
  const sender = new OutboundMessageSender();
  const session = { sock, status: 'connected' };

  const first = await sender.send('1', session, request());
  const duplicate = await sender.send('1', session, request());

  assert.equal(first.accepted, true);
  assert.equal(duplicate.accepted, true);
  assert.equal(duplicate.duplicate, true);
  assert.equal(sock.sendMessage.mock.callCount(), 1);
});

test('sender reports an ambiguous outcome after sendMessage starts', async () => {
  const sender = new OutboundMessageSender();
  const session = {
    status: 'connected',
    sock: {
      onWhatsApp: async () => [{ exists: true }],
      sendMessage: async () => { throw new Error('socket closed'); },
    },
  };

  const result = await sender.send('1', session, request());

  assert.equal(result.accepted, false);
  assert.equal(result.dispatch_started, true);
  assert.equal(result.outcome_unknown, true);
});

test('sender uses the persisted account LID for group membership checks', async () => {
  const sender = new OutboundMessageSender();
  const session = {
    status: 'connected',
    accountIdentity: {
      id: '971500000001:14@s.whatsapp.net',
      lid: '45617082548317:14@lid',
    },
    sock: {
      user: { id: '971500000001:14@s.whatsapp.net' },
      groupMetadata: async () => ({
        id: '120001@g.us',
        participants: [{ id: '45617082548317@lid' }],
      }),
      sendMessage: async () => ({ key: { id: 'provider-group-1' } }),
    },
  };

  const result = await sender.send('8', session, request({
    destination_jid: '120001@g.us',
    provider_message_id: 'outbound-group-1',
    content: { text: 'Group message' },
  }));

  assert.equal(result.accepted, true);
  assert.equal(result.destination_type, 'standard_group');
});

test('sender falls back to participating-group metadata before dispatch', async () => {
  const sender = new OutboundMessageSender();
  const metadata = {
    id: '120002@g.us',
    participants: [{ id: '45617082548317@lid' }],
  };
  const session = {
    status: 'connected',
    accountIdentity: { lid: '45617082548317:14@lid' },
    sock: {
      groupMetadata: async () => { throw new Error('forbidden'); },
      groupFetchAllParticipating: async () => ({ [metadata.id]: metadata }),
      sendMessage: test.mock.fn(async () => ({ key: { id: 'provider-group-2' } })),
    },
  };

  const result = await sender.send('8', session, request({
    destination_jid: metadata.id,
    provider_message_id: 'outbound-group-2',
  }));

  assert.equal(result.accepted, true);
  assert.equal(session.sock.sendMessage.mock.callCount(), 1);
});
