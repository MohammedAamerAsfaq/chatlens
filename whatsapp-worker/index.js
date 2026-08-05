'use strict';

require('dotenv').config();

const path = require('path');
const express = require('express');
const pino = require('pino');

const { SessionManager } = require('./src/session-manager');
const { DjangoClient } = require('./src/django-client');
const { MessageLogger } = require('./src/message-logger');
const sessionsRouter = require('./src/routes/sessions');

const PORT = parseInt(process.env.PORT || '3001', 10);
const DJANGO_BASE_URL = process.env.DJANGO_BASE_URL || 'http://localhost:8000';
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN || '';
const SESSION_STORE_PATH = process.env.SESSION_STORE_PATH || './sessions';
const MEDIA_STORE_PATH = process.env.MEDIA_STORE_PATH || './media';
const MESSAGE_LOGS_PATH = process.env.MESSAGE_LOGS_PATH || './message-logs';
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';
const HEARTBEAT_INTERVAL_MS = parseInt(process.env.WORKER_HEARTBEAT_INTERVAL_MS || '30000', 10);

const logger = pino({ level: LOG_LEVEL });

const djangoClient = new DjangoClient({
  baseUrl: DJANGO_BASE_URL,
  token: INTERNAL_API_TOKEN,
  logger,
  logsDir: MESSAGE_LOGS_PATH,
});

const messageLogger = new MessageLogger(MESSAGE_LOGS_PATH);

const sessionManager = new SessionManager({
  sessionStorePath: SESSION_STORE_PATH,
  djangoClient,
  messageLogger,
  logger,
});

function startHeartbeatLoop() {
  const sendHeartbeats = () => {
    for (const session of sessionManager.listSessions()) {
      djangoClient.sendWorkerHeartbeat(session.sessionId, {
        status: session.status,
        phone_number: session.phoneNumber,
        display_name: session.displayName,
      });
    }
  };

  sendHeartbeats();
  return setInterval(sendHeartbeats, HEARTBEAT_INTERVAL_MS);
}

// Root-cause fix for "an exception inside an async Baileys event handler dies with
// no persistent trace" — there was no top-level or process-level catch anywhere, so
// whatever was in flight when a handler threw was lost to stderr, which isn't
// captured anywhere durable. This can't identify which specific message/contact was
// in flight (Node doesn't expose that), but it makes the failure itself loud and
// durable instead of invisible — a fs.appendFileSync write (synchronous, so it
// completes before we decide whether to exit) plus a best-effort WorkerAlert.
//
// Deliberately NOT calling process.exit() here, unlike Node's usual uncaughtException
// guidance (crash and let a supervisor restart you) — this deployment's process
// management isn't something this fix controls, and an unexpected full-outage crash
// is itself a new failure mode we don't want to introduce sight-unseen. This trades
// "the process might now be in a slightly undefined state" for "it keeps serving
// every other session instead of going dark," which is the safer default here.
function _handleFatalProcessError(kind, err) {
  const detail = {
    kind,
    message: err?.message || String(err),
    stack: err?.stack || null,
    ts: new Date().toISOString(),
  };
  try {
    const fs = require('fs');
    const filePath = path.join(MESSAGE_LOGS_PATH, 'process-errors.ndjson');
    fs.appendFileSync(filePath, JSON.stringify(detail) + '\n', 'utf8');
  } catch (writeErr) {
    // stderr is the last resort if even the durable write fails
    console.error('Failed to write process-errors.ndjson', writeErr);
  }
  logger.error(detail, `Process-level ${kind} — see process-errors.ndjson`);
  try {
    djangoClient.sendWorkerAlert(null, {
      alert_type: 'uncaught_exception',
      severity: 'error',
      message: `${kind}: ${detail.message}`,
      context: { stack: detail.stack },
    });
  } catch { /* best-effort — the local file write above is the durable record either way */ }
}

process.on('uncaughtException', (err) => _handleFatalProcessError('uncaughtException', err));
process.on('unhandledRejection', (reason) => _handleFatalProcessError('unhandledRejection', reason instanceof Error ? reason : new Error(String(reason))));

const app = express();
app.use(express.json());

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Media files (downloaded from WhatsApp)
app.use('/media', express.static(path.resolve(MEDIA_STORE_PATH)));

// Sessions API
app.use('/sessions', sessionsRouter(sessionManager, MEDIA_STORE_PATH, messageLogger));

// 404
app.use((req, res) => res.status(404).json({ error: 'Not found' }));

// Error handler
app.use((err, req, res, _next) => {
  logger.error(err);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, async () => {
  logger.info(`ChatLens WhatsApp Worker running on port ${PORT}`);
  logger.info(`Django base URL: ${DJANGO_BASE_URL}`);
  await sessionManager.initialize();
  startHeartbeatLoop();
});
