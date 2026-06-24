'use strict';

require('dotenv').config();

const express = require('express');
const pino = require('pino');

const { SessionManager } = require('./src/session-manager');
const { DjangoClient } = require('./src/django-client');
const sessionsRouter = require('./src/routes/sessions');

const PORT = parseInt(process.env.PORT || '3001', 10);
const DJANGO_BASE_URL = process.env.DJANGO_BASE_URL || 'http://localhost:8000';
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN || '';
const SESSION_STORE_PATH = process.env.SESSION_STORE_PATH || './sessions';
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

const logger = pino({ level: LOG_LEVEL });

const djangoClient = new DjangoClient({
  baseUrl: DJANGO_BASE_URL,
  token: INTERNAL_API_TOKEN,
  logger,
});

const sessionManager = new SessionManager({
  sessionStorePath: SESSION_STORE_PATH,
  djangoClient,
  logger,
});

const app = express();
app.use(express.json());

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Sessions API
app.use('/sessions', sessionsRouter(sessionManager));

// 404
app.use((req, res) => res.status(404).json({ error: 'Not found' }));

// Error handler
app.use((err, req, res, _next) => {
  logger.error(err);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, () => {
  logger.info(`ChatLens WhatsApp Worker running on port ${PORT}`);
  logger.info(`Django base URL: ${DJANGO_BASE_URL}`);
});
