'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const sessionsRouter = require('../src/routes/sessions');

function findRoute(router, method, path) {
  return router.stack.find(layer => layer.route?.path === path && layer.route.methods[method]);
}

function makeResponse() {
  return {
    statusCode: 200,
    body: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(payload) {
      this.body = payload;
      return this;
    },
  };
}

test('POST /sessions forwards auto_download_media to createSession', async () => {
  const sessionManager = {
    createSession: test.mock.fn(async () => ({ status: 'pending_qr' })),
  };
  const router = sessionsRouter(
    sessionManager,
    '.',
    { read: () => ({}), clear: () => {} },
    'test-token',
  );
  const route = findRoute(router, 'post', '/');
  assert.ok(route, 'expected POST / route to exist');

  const req = {
    body: {
      session_id: 'account-1',
      sync_history: true,
      history_days: 7,
      idle_disconnect_minutes: 15,
      auto_download_media: false,
    },
  };
  const res = makeResponse();

  await route.route.stack[0].handle(req, res);

  assert.equal(res.statusCode, 201);
  assert.equal(sessionManager.createSession.mock.callCount(), 1);
  assert.deepEqual(sessionManager.createSession.mock.calls[0].arguments, [
    'account-1',
    {
      sync_history: true,
      history_days: 7,
      idle_disconnect_minutes: 15,
      auto_download_media: false,
    },
  ]);
});

test('POST destination preflight is dry-run delegated to session manager', async () => {
  const sessionManager = {
    preflightDestination: test.mock.fn(async () => ({
      destination_type: 'direct_contact',
      recipient_registered: true,
    })),
  };
  const router = sessionsRouter(
    sessionManager,
    '.',
    { read: () => ({}), clear: () => {} },
    'test-token',
  );
  const route = findRoute(router, 'post', '/:id/destinations/preflight');
  assert.ok(route, 'expected destination preflight route to exist');

  const req = {
    params: { id: 'account-1' },
    body: { destination_jid: '971500000001@s.whatsapp.net' },
    headers: { 'x-internal-token': 'test-token' },
  };
  const res = makeResponse();

  await route.route.stack[0].handle(req, res);

  assert.equal(res.statusCode, 200);
  assert.equal(sessionManager.preflightDestination.mock.callCount(), 1);
  assert.deepEqual(sessionManager.preflightDestination.mock.calls[0].arguments, [
    'account-1',
    '971500000001@s.whatsapp.net',
  ]);
});

test('POST destination preflight rejects an invalid internal token', async () => {
  const sessionManager = {
    preflightDestination: test.mock.fn(async () => ({})),
  };
  const router = sessionsRouter(
    sessionManager,
    '.',
    { read: () => ({}), clear: () => {} },
    'test-token',
  );
  const route = findRoute(router, 'post', '/:id/destinations/preflight');
  const res = makeResponse();

  await route.route.stack[0].handle({ params: { id: 'account-1' }, body: {}, headers: {} }, res);

  assert.equal(res.statusCode, 401);
  assert.equal(sessionManager.preflightDestination.mock.callCount(), 0);
});

test('POST messages authenticates and delegates durable outbound transport', async () => {
  const sessionManager = {
    sendOutboundMessage: test.mock.fn(async () => ({ accepted: true, dispatch_started: true })),
  };
  const router = sessionsRouter(sessionManager, '.', { read: () => ({}), clear: () => {} }, 'test-token');
  const route = findRoute(router, 'post', '/:id/messages');
  const req = {
    params: { id: 'account-1' },
    headers: { 'x-internal-token': 'test-token' },
    body: {
      outbound_message_id: 4,
      provider_message_id: 'fixed-id',
      destination_jid: '971500000001@s.whatsapp.net',
      content_type: 'text',
      content: { text: 'Hello' },
    },
  };
  const res = makeResponse();

  await route.route.stack[0].handle(req, res);

  assert.equal(res.statusCode, 200);
  assert.equal(sessionManager.sendOutboundMessage.mock.callCount(), 1);
});

test('POST capacity refresh returns telemetry without sending a message', async () => {
  const sessionManager = {
    getCapacityTelemetry: test.mock.fn(async () => ({
      source: 'baileys_v7',
      cap: { status: 'available', data: { total_quota: 10, used_quota: 2 } },
    })),
  };
  const router = sessionsRouter(
    sessionManager,
    '.',
    { read: () => ({}), clear: () => {} },
    'test-token',
  );
  const route = findRoute(router, 'post', '/:id/capacity/refresh');
  const res = makeResponse();

  await route.route.stack[0].handle({
    params: { id: 'account-1' },
    body: {},
    headers: { 'x-internal-token': 'test-token' },
  }, res);

  assert.equal(res.statusCode, 200);
  assert.equal(res.body.cap.data.total_quota, 10);
  assert.equal(sessionManager.getCapacityTelemetry.mock.callCount(), 1);
});
