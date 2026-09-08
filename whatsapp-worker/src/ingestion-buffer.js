'use strict';

const fs = require('fs');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');

class IngestionBuffer {
  constructor({ databasePath, logger, maxAttempts = 12, retryBaseMs = 1000, retryMaxMs = 300000 }) {
    this.databasePath = databasePath;
    this.logger = logger;
    this.maxAttempts = maxAttempts;
    this.retryBaseMs = retryBaseMs;
    this.retryMaxMs = retryMaxMs;
    fs.mkdirSync(path.dirname(databasePath), { recursive: true });
    this.db = new DatabaseSync(databasePath);
    this.db.exec('PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS ingestion_event (
        id INTEGER PRIMARY KEY,
        session_id TEXT NOT NULL,
        provider_message_id TEXT NULL,
        event_type TEXT NOT NULL,
        raw_jid TEXT NULL,
        participant_jid TEXT NULL,
        from_me INTEGER NULL,
        message_time TEXT NULL,
        raw_payload TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        available_at TEXT NOT NULL,
        last_error TEXT NOT NULL DEFAULT '',
        last_attempt_at TEXT NULL,
        created_at TEXT NOT NULL,
        delivered_at TEXT NULL
      );
      CREATE UNIQUE INDEX IF NOT EXISTS ingestion_event_unique_provider
      ON ingestion_event(session_id, provider_message_id)
      WHERE provider_message_id IS NOT NULL;
      CREATE INDEX IF NOT EXISTS ingestion_event_dispatch_idx
      ON ingestion_event(status, available_at, created_at);
    `);
    // A process stop cannot know whether an HTTP request completed. Resetting to
    // pending is safe because Django has final message-level idempotency.
    this.db.prepare("UPDATE ingestion_event SET status = 'pending', available_at = ?, last_error = 'Dispatcher restarted while delivering.' WHERE status = 'delivering'")
      .run(new Date().toISOString());
  }

  enqueue({ sessionId, providerMessageId = null, eventType = 'message_ingest', rawJid = null, participantJid = null, fromMe = null, messageTime = null, rawPayload }) {
    if (!sessionId || !rawPayload || typeof rawPayload !== 'object') {
      throw new Error('Ingestion Event requires sessionId and object rawPayload.');
    }
    const now = new Date().toISOString();
    const result = this.db.prepare(`
      INSERT OR IGNORE INTO ingestion_event
      (session_id, provider_message_id, event_type, raw_jid, participant_jid, from_me, message_time, raw_payload, status, attempts, available_at, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
    `).run(
      sessionId, providerMessageId, eventType, rawJid, participantJid,
      fromMe === null ? null : (fromMe ? 1 : 0), messageTime,
      JSON.stringify(rawPayload), now, now,
    );
    if (result.changes === 0 && providerMessageId) {
      const existing = this.db.prepare('SELECT id FROM ingestion_event WHERE session_id = ? AND provider_message_id = ?').get(sessionId, providerMessageId);
      return { id: existing.id, duplicate: true };
    }
    return { id: Number(result.lastInsertRowid), duplicate: false };
  }

  claimDue(limit = 20) {
    const now = new Date().toISOString();
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const rows = this.db.prepare(`
        SELECT * FROM ingestion_event
        WHERE status = 'pending' AND available_at <= ?
        ORDER BY available_at, created_at, id LIMIT ?
      `).all(now, limit);
      const claim = this.db.prepare(`
        UPDATE ingestion_event SET status = 'delivering', attempts = attempts + 1, last_attempt_at = ?
        WHERE id = ? AND status = 'pending'
      `);
      const claimed = [];
      for (const row of rows) {
        if (claim.run(now, row.id).changes) {
          claimed.push({ ...row, attempts: row.attempts + 1, status: 'delivering', last_attempt_at: now });
        }
      }
      this.db.exec('COMMIT');
      return claimed;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  markDelivered(id) {
    const now = new Date().toISOString();
    this.db.prepare("UPDATE ingestion_event SET status = 'delivered', delivered_at = ?, last_error = '' WHERE id = ?").run(now, id);
  }

  replacePayload(id, { eventType, rawPayload, rawJid = null, messageTime = null }) {
    const result = this.db.prepare(`
      UPDATE ingestion_event
      SET event_type = ?, raw_payload = ?, raw_jid = ?, message_time = ?, last_error = ''
      WHERE id = ? AND status != 'delivered'
    `).run(eventType, JSON.stringify(rawPayload), rawJid, messageTime, id);
    if (!result.changes) throw new Error(`Ingestion Event ${id} cannot be prepared for delivery.`);
  }

  markBuildFailed(id, error) {
    const message = error instanceof Error ? error.message : String(error);
    this.db.prepare("UPDATE ingestion_event SET status = 'failed', last_error = ?, last_attempt_at = ? WHERE id = ?")
      .run(`Payload normalization failed: ${message}`, new Date().toISOString(), id);
  }

  markDeliveryFailed(event, error) {
    const message = error instanceof Error ? error.message : String(error);
    const now = new Date();
    if (event.attempts >= this.maxAttempts) {
      this.db.prepare("UPDATE ingestion_event SET status = 'failed', last_error = ?, last_attempt_at = ? WHERE id = ?")
        .run(message, now.toISOString(), event.id);
      return { retrying: false };
    }
    const delay = Math.min(this.retryBaseMs * (2 ** Math.max(0, event.attempts - 1)), this.retryMaxMs);
    this.db.prepare("UPDATE ingestion_event SET status = 'pending', available_at = ?, last_error = ?, last_attempt_at = ? WHERE id = ?")
      .run(new Date(now.getTime() + delay).toISOString(), message, now.toISOString(), event.id);
    return { retrying: true, delay };
  }

  diagnostics() {
    const counts = this.db.prepare('SELECT status, COUNT(*) AS count FROM ingestion_event GROUP BY status').all();
    const oldest = this.db.prepare("SELECT MIN(created_at) AS oldest FROM ingestion_event WHERE status IN ('pending', 'delivering')").get();
    return { counts, oldest_undelivered_at: oldest?.oldest || null };
  }

  close() { this.db.close(); }
}


class IngestionDispatcher {
  constructor({ buffer, deliver, logger, intervalMs = 1000, batchSize = 20 }) {
    this.buffer = buffer;
    this.deliver = deliver;
    this.logger = logger;
    this.intervalMs = intervalMs;
    this.batchSize = batchSize;
    this.timer = null;
    this.running = false;
  }

  async dispatchOnce() {
    const events = this.buffer.claimDue(this.batchSize);
    for (const event of events) {
      try {
        const payload = JSON.parse(event.raw_payload);
        if (payload._pending_normalization) {
          throw new Error('Ingestion Event is awaiting payload normalization.');
        }
        const response = await this.deliver(event, payload);
        if (!response || response.success !== true) {
          throw new Error('Django did not explicitly confirm ingestion persistence.');
        }
        this.buffer.markDelivered(event.id);
        this.logger.debug({ ingestionEventId: event.id, providerMessageId: event.provider_message_id }, 'Ingestion Dispatcher delivered event');
      } catch (error) {
        const outcome = this.buffer.markDeliveryFailed(event, error);
        this.logger.warn({ ingestionEventId: event.id, providerMessageId: event.provider_message_id, error: error.message, ...outcome }, 'Ingestion Dispatcher delivery failed');
      }
    }
    return events.length;
  }

  start() {
    if (this.timer) return;
    const tick = async () => {
      if (this.running) return;
      this.running = true;
      try { await this.dispatchOnce(); }
      catch (error) { this.logger.error({ error: error.message }, 'Ingestion Dispatcher poll failed'); }
      finally { this.running = false; }
    };
    tick();
    this.timer = setInterval(tick, this.intervalMs);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}

module.exports = { IngestionBuffer, IngestionDispatcher };
