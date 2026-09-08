'use strict';

require('dotenv').config();

const { IngestionBuffer, IngestionDispatcher } = require('./src/ingestion-buffer');
const { DjangoClient } = require('./src/django-client');

const logger = require('pino')({ level: process.env.LOG_LEVEL || 'info' });
const databasePath = process.env.INGESTION_BUFFER_PATH || './ingestion-buffer/ingestion.sqlite';
const djangoClient = new DjangoClient({
  baseUrl: process.env.DJANGO_BASE_URL || 'http://localhost:8000',
  token: process.env.INTERNAL_API_TOKEN || '',
  logger,
  logsDir: process.env.MESSAGE_LOGS_PATH || './message-logs',
});
const buffer = new IngestionBuffer({ databasePath, logger });
const dispatcher = new IngestionDispatcher({
  buffer,
  deliver: (event, payload) => {
    if (event.event_type === 'message_ingest_batch') {
      return djangoClient.sendMessageIngestBatch(
        payload.worker_session_id,
        payload.messages,
        { isLatest: payload.is_latest, received: payload.received },
      );
    }
    return djangoClient.sendMessageIngest(payload);
  },
  logger,
  intervalMs: parseInt(process.env.INGESTION_DISPATCH_INTERVAL_MS || '1000', 10),
});

dispatcher.start();
logger.info({ databasePath }, 'Ingestion Dispatcher started');

function stop() {
  dispatcher.stop();
  buffer.close();
  process.exit(0);
}

process.on('SIGINT', stop);
process.on('SIGTERM', stop);
