'use strict';

function closeServer(server, timeoutMs) {
  if (!server?.listening) return Promise.resolve();
  return new Promise((resolve) => {
    let complete = false;
    const finish = () => {
      if (complete) return;
      complete = true;
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(() => {
      server.closeAllConnections?.();
      finish();
    }, timeoutMs);
    server.close(finish);
    server.closeIdleConnections?.();
  });
}

async function waitForDispatcher(dispatcher, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (dispatcher.running && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 25));
  }
  if (dispatcher.running) {
    throw new Error('Ingestion Dispatcher did not stop before the shutdown deadline.');
  }
}

function createGracefulShutdown({
  server,
  stopHeartbeat,
  dispatcher,
  sessionManager,
  ingestionBuffer,
  logger,
  timeoutMs = 20000,
  exit = code => process.exit(code),
}) {
  let shutdownPromise = null;

  return function shutdown(signal = 'shutdown') {
    if (shutdownPromise) return shutdownPromise;

    shutdownPromise = (async () => {
      logger.info({ signal }, 'Graceful WhatsApp worker shutdown started');
      stopHeartbeat();
      dispatcher.stop();

      const serverClosed = closeServer(server, Math.min(5000, timeoutMs));
      await sessionManager.shutdown();
      await waitForDispatcher(dispatcher, Math.min(10000, timeoutMs));
      await serverClosed;
      ingestionBuffer.close();
      logger.info('Graceful WhatsApp worker shutdown completed');
    })();

    const deadline = setTimeout(() => {
      logger.error({ timeoutMs }, 'Graceful shutdown deadline exceeded; forcing process exit');
      exit(1);
    }, timeoutMs);

    shutdownPromise.then(
      () => {
        clearTimeout(deadline);
        logger.flush?.();
        exit(0);
      },
      (error) => {
        clearTimeout(deadline);
        logger.error({ error: error.message }, 'Graceful shutdown failed');
        logger.flush?.();
        exit(1);
      },
    );
    return shutdownPromise;
  };
}

module.exports = { createGracefulShutdown };
