'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { createGracefulShutdown } = require('../src/graceful-shutdown');

function mockFunction(implementation = () => {}) {
  return test.mock.fn(implementation);
}

test('graceful shutdown drains resources and exits successfully once', async () => {
  const exit = mockFunction();
  const stopHeartbeat = mockFunction();
  const dispatcher = { running: false, stop: mockFunction() };
  const sessionManager = { shutdown: mockFunction(async () => {}) };
  const ingestionBuffer = { close: mockFunction() };
  const server = {
    listening: true,
    close: mockFunction(callback => callback()),
    closeIdleConnections: mockFunction(),
  };
  const logger = { info: mockFunction(), error: mockFunction(), flush: mockFunction() };
  const shutdown = createGracefulShutdown({
    server, stopHeartbeat, dispatcher, sessionManager, ingestionBuffer,
    logger, timeoutMs: 100, exit,
  });

  const first = shutdown('SIGTERM');
  const second = shutdown('SIGINT');
  assert.equal(first, second);
  await first;
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(stopHeartbeat.mock.callCount(), 1);
  assert.equal(dispatcher.stop.mock.callCount(), 1);
  assert.equal(sessionManager.shutdown.mock.callCount(), 1);
  assert.equal(ingestionBuffer.close.mock.callCount(), 1);
  assert.equal(exit.mock.callCount(), 1);
  assert.equal(exit.mock.calls[0].arguments[0], 0);
});

test('graceful shutdown exits with failure when dispatcher cannot drain', async () => {
  const exit = mockFunction();
  const dispatcher = { running: true, stop: mockFunction() };
  const shutdown = createGracefulShutdown({
    server: { listening: false },
    stopHeartbeat: mockFunction(),
    dispatcher,
    sessionManager: { shutdown: mockFunction(async () => {}) },
    ingestionBuffer: { close: mockFunction() },
    logger: { info: mockFunction(), error: mockFunction(), flush: mockFunction() },
    timeoutMs: 20,
    exit,
  });

  await assert.rejects(shutdown('SIGTERM'), /did not stop/);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(exit.mock.calls[0].arguments[0], 1);
});
