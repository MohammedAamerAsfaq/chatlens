'use strict';

const fs = require('fs');
const path = require('path');
const axios = require('axios');

class DjangoClient {
  constructor({ baseUrl, token, logger, logsDir = null }) {
    this.logger = logger;
    this.logsDir = logsDir;
    this.http = axios.create({
      baseURL: baseUrl,
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Token': token,
      },
      timeout: 10000,
    });
  }

  // Last-resort local record for the two safety-net reports (dropped messages,
  // worker alerts) when Django itself can't be reached — the exact moment those
  // reports matter most is when something is already going wrong, so their own
  // failure path must not be a second silent hole. Best-effort: if even this
  // write fails (disk full, permissions), there is nothing further to fall back
  // to, but that failure is itself logged at 'error', never swallowed.
  _writeFallback(kind, payload) {
    if (!this.logsDir) return;
    try {
      const filePath = path.join(this.logsDir, 'failed-reports.ndjson');
      const line = { ts: new Date().toISOString(), kind, payload };
      fs.appendFileSync(filePath, JSON.stringify(line) + '\n', 'utf8');
    } catch (err) {
      this.logger.error({ kind, err: err.message }, 'Failed to write local fallback report — report is fully lost');
    }
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

  async sendMessageIngestBatch(sessionId, payloads, { isLatest = false, received = payloads.length } = {}) {
    const resp = await this.http.post('/api/internal/whatsapp/message-ingest-batch/', {
      worker_session_id: sessionId,
      messages: payloads,
      is_latest: isLatest,
      received,
    });
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

  async getLidMappings(sessionId) {
    try {
      const resp = await this.http.get(
        `/api/internal/whatsapp/lid-mappings/${sessionId}/`,
      );
      return {
        lidToPhone: resp.data.lid_to_phone || {},
        usernameToPhone: resp.data.username_to_phone || {},
      };
    } catch (err) {
      this.logger.warn({ sessionId, error: err.message }, 'Could not fetch LID mappings — starting with empty cache');
      return { lidToPhone: {}, usernameToPhone: {} };
    }
  }

  async sendDroppedMessage(sessionId, fields) {
    const payload = { worker_session_id: sessionId, ...fields };
    try {
      await this.http.post('/api/internal/whatsapp/dropped-message/', payload);
    } catch (err) {
      // This is the safety net for lost messages — its own failure must be loud,
      // not debug-level noise nobody sees, and must not be the second silent hole
      // on top of whatever already went wrong.
      this.logger.warn({ sessionId, reason: fields.reason, err: err.message }, 'sendDroppedMessage failed — falling back to local file');
      this._writeFallback('dropped_message', payload);
    }
  }

  async sendWorkerAlert(sessionId, fields) {
    const payload = { worker_session_id: sessionId, ...fields };
    try {
      await this.http.post('/api/internal/whatsapp/worker-alert/', payload);
    } catch (err) {
      this.logger.warn({ sessionId, alertType: fields.alert_type, err: err.message }, 'sendWorkerAlert failed — falling back to local file');
      this._writeFallback('worker_alert', payload);
    }
  }

  async sendStuckReceipt(sessionId, fields) {
    const payload = { worker_session_id: sessionId, ...fields };
    try {
      await this.http.post('/api/internal/whatsapp/stuck-receipt/', payload);
    } catch (err) {
      this.logger.warn({ sessionId, messageId: fields.message_id, err: err.message }, 'sendStuckReceipt failed — falling back to local file');
      this._writeFallback('stuck_receipt', payload);
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

  async sendGroupUpdate(sessionId, groupPayload) {
    try {
      await this.http.post('/api/internal/whatsapp/group-update/', {
        worker_session_id: sessionId,
        ...groupPayload,
      });
    } catch (err) {
      this.logger.warn(
        { sessionId, groupId: groupPayload.group_id, error: err.message },
        'Failed to send group update to Django',
      );
    }
  }

  async sendGroupParticipantsUpdate(sessionId, groupId, action, participants) {
    try {
      await this.http.post('/api/internal/whatsapp/group-participants-update/', {
        worker_session_id: sessionId,
        group_id: groupId,
        action,
        participants,
      });
    } catch (err) {
      this.logger.warn(
        { sessionId, groupId, action, error: err.message },
        'Failed to send group participants update to Django',
      );
    }
  }
}

module.exports = { DjangoClient };
