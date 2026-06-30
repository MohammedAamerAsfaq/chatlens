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
      throw err; // rethrow so _forwardMessage can detect the failure and report it
    }
  }

  async sendMessageIngestBatch(payloads) {
    const resp = await this.http.post('/api/internal/whatsapp/message-ingest-batch/', { messages: payloads });
    return resp.data;
  }

  async getAccountSettings(sessionId) {
    try {
      const resp = await this.http.get(
        `/api/internal/whatsapp/account-settings/${sessionId}/`,
      );
      return resp.data;
    } catch (err) {
      this.logger.warn({ sessionId, error: err.message }, 'Could not fetch account settings — using defaults');
      return { sync_history: true, history_days: null, idle_disconnect_minutes: 0 };
    }
  }

  async sendDroppedMessage(sessionId, fields) {
    try {
      await this.http.post('/api/internal/whatsapp/dropped-message/', {
        worker_session_id: sessionId,
        ...fields,
      });
    } catch (err) {
      // fire-and-forget — log at debug so this never spams error output
      this.logger.debug({ sessionId, reason: fields.reason, err: err.message }, 'sendDroppedMessage failed');
    }
  }

  async sendContactsUpdate(sessionId, contacts) {
    if (!contacts.length) return;
    try {
      await this.http.post('/api/internal/whatsapp/contacts-update/', {
        worker_session_id: sessionId,
        contacts,
      });
      this.logger.info({ sessionId, count: contacts.length }, 'Contacts update sent to Django');
    } catch (err) {
      this.logger.warn(
        { sessionId, error: err.message },
        'Failed to send contacts update to Django',
      );
    }
  }
}

module.exports = { DjangoClient };
