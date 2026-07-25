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
  const router = sessionsRouter(sessionManager, '.', { read: () => ({}), clear: () => {} });
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
