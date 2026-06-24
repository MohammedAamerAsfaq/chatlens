'use strict';

const axios = require('axios');

class DjangoClient {
  constructor({ baseUrl, token, logger }) {
    this.logger = logger;
    this.http = axios.create({
      baseURL: baseUrl,
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Token': token,
      },
      timeout: 10000,
    });
  }

  async sendSessionStatus(sessionId, fields) {
    const payload = {
      worker_session_id: sessionId,
      event_time: new Date().toISOString(),
      ...fields,
    };

    try {
      await this.http.post('/api/internal/whatsapp/session-status/', payload);
      this.logger.info({ sessionId, status: fields.status }, 'Session status sent to Django');
    } catch (err) {
      this.logger.error(
        { sessionId, status: fields.status, error: err.message },
        'Failed to send session status to Django',
      );
    }
  }

  async sendMessageIngest(payload) {
    try {
      await this.http.post('/api/internal/whatsapp/message-ingest/', payload);
    } catch (err) {
      this.logger.error(
        { msgId: payload.provider_message_id, error: err.message },
        'Failed to send message to Django',
      );
    }
  }
}

module.exports = { DjangoClient };
