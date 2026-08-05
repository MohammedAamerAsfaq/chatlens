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
      const filePath = this._fallbackPath();
      const line = { ts: new Date().toISOString(), kind, payload };
      fs.appendFileSync(filePath, JSON.stringify(line) + '\n', 'utf8');
    } catch (err) {
      this.logger.error({ kind, err: err.message }, 'Failed to write local fallback report — report is fully lost');
    }
  }

  _fallbackPath() {
    return path.join(this.logsDir, 'failed-reports.ndjson');
  }

  _httpErrorLogFields(err) {
    return {
      err: err.message,
      statusCode: err.response?.status || null,
      responseBody: err.response?.data || null,
    };
  }

  async _postReplayRecord(record) {
    const payload = record.payload || {};
    if (record.kind === 'contacts_update') {
      await this.http.post('/api/internal/whatsapp/contacts-update/', payload);
      return { status: 'replayed' };
    }
    if (record.kind === 'group_update') {
      await this.http.post('/api/internal/whatsapp/group-update/', payload);
      return { status: 'replayed' };
    }
    if (record.kind === 'group_participants_update') {
      if (payload.action === 'modify') {
        return {
          status: 'discarded',
          reason: 'group_participants_modify_is_replay_unsafe',
        };
      }
      await this.http.post('/api/internal/whatsapp/group-participants-update/', payload);
      return { status: 'replayed' };
    }
    return { status: 'retained', reason: 'unknown_fallback_kind' };
  }

  async replayFallbackReports() {
    if (!this.logsDir) return { attempted: 0, replayed: 0, retained: 0, discarded: 0 };

    const filePath = this._fallbackPath();
    if (!fs.existsSync(filePath)) return { attempted: 0, replayed: 0, retained: 0, discarded: 0 };

    let lines;
    try {
      lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/).filter(Boolean);
    } catch (err) {
      this.logger.error({ err: err.message }, 'Failed to read fallback report file');
      return { attempted: 0, replayed: 0, retained: 0, discarded: 0 };
    }

    const retained = [];
    let attempted = 0;
    let replayed = 0;
    let discarded = 0;

    for (const line of lines) {
      let record;
      try {
        record = JSON.parse(line);
      } catch (err) {
        this.logger.error({ err: err.message }, 'Invalid fallback report line retained for inspection');
        retained.push(line);
        continue;
      }

      try {
        const replayResult = await this._postReplayRecord(record);
        if (replayResult.status === 'retained') {
          this.logger.warn(
            {
              kind: record.kind,
              reason: replayResult.reason,
            },
            'Fallback report replay skipped - retaining record',
          );
          retained.push(line);
          continue;
        }
        if (replayResult.status === 'discarded') {
          discarded += 1;
          this.logger.warn(
            {
              kind: record.kind,
              reason: replayResult.reason,
              sessionId: record.payload?.worker_session_id,
              groupId: record.payload?.group_id,
              action: record.payload?.action,
            },
            'Fallback report replay skipped - discarding replay-unsafe record',
          );
          continue;
        }
        if (replayResult.status === 'replayed') {
          attempted += 1;
          replayed += 1;
        }
      } catch (err) {
        attempted += 1;
        retained.push(line);
        this.logger.warn(
          {
            kind: record.kind,
            sessionId: record.payload?.worker_session_id,
            groupId: record.payload?.group_id,
            action: record.payload?.action,
            ...this._httpErrorLogFields(err),
          },
          'Fallback report replay failed - retaining record',
        );
      }
    }

    try {
      if (retained.length) {
        fs.writeFileSync(filePath, retained.join('\n') + '\n', 'utf8');
      } else {
        fs.unlinkSync(filePath);
      }
    } catch (err) {
      this.logger.error({ err: err.message }, 'Failed to update fallback report file after replay');
    }

    if (attempted || replayed || discarded) {
      this.logger.info({ attempted, replayed, retained: retained.length, discarded }, 'Fallback report replay completed');
    }
    return { attempted, replayed, retained: retained.length, discarded };
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

  async sendWorkerHeartbeat(sessionId, fields = {}) {
    const payload = {
      worker_session_id: sessionId,
      event_time: new Date().toISOString(),
      ...fields,
    };

    try {
      await this.http.post('/api/internal/whatsapp/worker-heartbeat/', payload);
      this.logger.debug({ sessionId, status: fields.status }, 'Worker heartbeat sent to Django');
    } catch (err) {
      this.logger.warn(
        { sessionId, status: fields.status, error: err.message },
        'Failed to send worker heartbeat to Django',
      );
    }
  }

  async sendMessageIngest(payload) {
    try {
      const resp = await this.http.post('/api/internal/whatsapp/message-ingest/', payload);
      return resp.data;
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

  // Resolution source 3 for outbound/cache-miss LID resolution (see
  // 'docs/Contact Message Loss — LID Resolution Fix Proposal.md' Fix 2) — a
  // narrow single-LID lookup against Django's persisted whatsapp_contact.lid_jid,
  // used when session.lidToPhone misses. Deliberately NOT wrapped in try/catch
  // here: this is on the critical resolution path, and per the P0 message-
  // preservation spec a failure here must be explicit to the caller (which
  // decides whether to fall through to preserving the message as unresolved),
  // never silently treated as "not found". Bounded by the shared axios
  // `timeout: 10000` above — one slow/failed lookup can't hang the caller
  // indefinitely.
  async lookupLidMapping(sessionId, lidJid) {
    const resp = await this.http.get(
      `/api/internal/whatsapp/lid-mapping/${sessionId}/`,
      { params: { lid_jid: lidJid } },
    );
    return resp.data; // { found: true, lid_jid, phone_jid } | { found: false }
  }

  // Durable preservation for a message with real content whose LID couldn't be
  // resolved (see WhatsAppUnresolvedMessage). Deliberately NOT wrapped in
  // try/catch and deliberately has NO local-file fallback on failure, unlike
  // sendDroppedMessage/sendWorkerAlert/sendStuckReceipt above — per the P0
  // message-preservation spec (§16), this path must never let the worker
  // believe a message is "safely preserved" when Django persistence actually
  // failed. The caller is responsible for treating a thrown error here as a
  // real failure (WorkerAlert), not a second silent fallback path.
  async sendUnresolvedMessage(sessionId, payload) {
    const resp = await this.http.post('/api/internal/whatsapp/unresolved-message/', {
      worker_session_id: sessionId,
      ...payload,
    });
    return resp.data; // { success: true, id, resolution_status }
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

  async sendBaileysEvent(sessionId, fields) {
    const payload = { worker_session_id: sessionId, ...fields };
    try {
      await this.http.post('/api/internal/whatsapp/baileys-event/', payload);
    } catch (err) {
      this.logger.warn(
        {
          sessionId,
          eventType: fields.event_type,
          msgId: fields.provider_message_id,
          err: err.message,
        },
        'sendBaileysEvent failed - event was not persisted',
      );
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
    const payload = {
      worker_session_id: sessionId,
      contacts,
    };
    try {
      const resp = await this.http.post('/api/internal/whatsapp/contacts-update/', payload);
      const updated = resp.data?.updated;
      const skipped = resp.data?.skipped || 0;
      const rejected = resp.data?.rejected || 0;
      this.logger.info({ sessionId, count: contacts.length, updated, skipped, rejected }, 'Contacts update sent to Django');
      if (rejected > 0) {
        this.logger.warn({ sessionId, rejected, skipped }, 'Contacts update completed with rejected records');
      }
    } catch (err) {
      this.logger.warn(
        { sessionId, error: err.message },
        'Failed to send contacts update to Django - falling back to local file',
      );
      this._writeFallback('contacts_update', payload);
    }
  }

  async sendGroupUpdate(sessionId, groupPayload) {
    const payload = {
      worker_session_id: sessionId,
      ...groupPayload,
    };
    try {
      await this.http.post('/api/internal/whatsapp/group-update/', payload);
    } catch (err) {
      this.logger.warn(
        { sessionId, groupId: groupPayload.group_id, error: err.message },
        'Failed to send group update to Django - falling back to local file',
      );
      this._writeFallback('group_update', payload);
    }
  }

  async sendGroupParticipantsUpdate(sessionId, groupId, action, participants) {
    const payload = {
      worker_session_id: sessionId,
      group_id: groupId,
      action,
      participants,
    };
    try {
      await this.http.post('/api/internal/whatsapp/group-participants-update/', payload);
    } catch (err) {
      this.logger.warn(
        { sessionId, groupId, action, error: err.message },
        'Failed to send group participants update to Django - falling back to local file',
      );
      this._writeFallback('group_participants_update', payload);
    }
  }
}

module.exports = { DjangoClient };
