'use strict';

const path = require('path');
const fs = require('fs');
const {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  isJidBroadcast,
  jidNormalizedUser,
  downloadMediaMessage,
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const QRCode = require('qrcode');

const SESSION_STATUS = {
  PENDING_QR:    'pending_qr',
  QR_GENERATED:  'qr_generated',
  CONNECTED:     'connected',
  DISCONNECTED:  'disconnected',
  LOGGED_OUT:    'logged_out',
  ERROR:         'error',
};

// If no connection.update event (qr/open/close) arrives within this window, the
// handshake is considered hung. Generous enough that a normal QR generation or a
// legitimate wait-for-scan (Baileys re-fires 'qr' periodically, which re-arms this)
// never trips it — only a truly stalled socket does.
const WATCHDOG_TIMEOUT_MS = 45000;

// Base delay and cap for exponential-backoff reconnects (see 'close' handler below).
// A flat retry interval hammers WhatsApp's servers during any outage — the kind of
// pattern that gets a linked device flagged/rate-limited, which is itself a way to
// end up forced into a fresh QR re-link. Backing off preserves the existing session
// for as long as possible instead.
const RECONNECT_BASE_DELAY_MS = 5000;
const RECONNECT_MAX_DELAY_MS = 5 * 60 * 1000;

// A session can report 'connected' (WhatsApp mobile shows the linked device as active)
// while its LOCAL copy of the Signal-protocol session is desynced enough that it can't
// actually decrypt anything, or WhatsApp's post-connect handshake keeps timing out.
// Reconnecting doesn't fix either — it reuses the same corrupted key state on disk — so
// past these thresholds (counted since the last successfully-forwarded message, not a
// time window) the session is flagged connection_unhealthy for the UI (needs re-link).
// This is a SEPARATE, higher-level signal from the per-occurrence WorkerAlert below —
// every single failure gets an alert immediately; this threshold only escalates to
// "the whole session likely needs attention" after they don't stop happening.
const DECRYPT_FAILURE_UNHEALTHY_THRESHOLD = 15;
const INIT_QUERY_TIMEOUT_UNHEALTHY_THRESHOLD = 5;

// TEMPORARY debugging aid — investigating messages from a specific contact
// (971521962376 / Al Thamam Ipad Almurar) vanishing with no trace in any of the
// normal drop-reporting paths. Logs the full raw Baileys event unconditionally,
// bypassing every filter, so the next occurrence gets captured no matter what
// shape it arrives in (unknown message type, rotated LID, exception before any
// _reportDropped call, etc.). Remove once the mechanism is confirmed.
// TODO: remove after root cause for 971521962376 is confirmed (see conversation 2026-07-06).
const DEBUG_WATCH_JIDS = ['43190593786026@lid', '971521962376@s.whatsapp.net'];
const DEBUG_WATCH_NAME_HINT = 'thamam';

function _isDebugWatchTarget(msg) {
  const key = msg?.key || {};
  const candidates = [key.remoteJid, key.participant, key.participantPn, key.senderPn].filter(Boolean);
  if (candidates.some(jid => DEBUG_WATCH_JIDS.includes(jid))) return true;
  const name = (msg?.pushName || '').toLowerCase();
  return name.includes(DEBUG_WATCH_NAME_HINT);
}

const MIME_TO_EXT = {
  'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif',
  'video/mp4': 'mp4', 'video/3gpp': '3gp', 'video/mpeg': 'mpeg',
  'audio/ogg': 'ogg', 'audio/mpeg': 'mp3', 'audio/mp4': 'm4a', 'audio/aac': 'aac',
  'application/pdf': 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
  'application/zip': 'zip',
  'image/webp; codecs=vp9': 'webp',
};

class SessionManager {
  constructor({ sessionStorePath, djangoClient, messageLogger, logger }) {
    this.sessionStorePath = sessionStorePath;
    this.mediaStorePath = path.join(path.dirname(sessionStorePath), 'media');
    this.djangoClient = djangoClient;
    this.messageLogger = messageLogger;
    this.logger = logger;
    // Map<sessionId, { sock, status, qrDataUrl, phoneNumber, displayName }>
    this.sessions = new Map();
    // Cache group names to avoid repeated API calls
    this.groupNameCache = new Map();

    if (!fs.existsSync(sessionStorePath)) {
      fs.mkdirSync(sessionStorePath, { recursive: true });
    }
    if (!fs.existsSync(this.mediaStorePath)) {
      fs.mkdirSync(this.mediaStorePath, { recursive: true });
    }
  }

  _mimeToExt(mime) {
    if (!mime) return 'bin';
    const base = mime.split(';')[0].trim();
    if (MIME_TO_EXT[base]) return MIME_TO_EXT[base];
    const sub = base.split('/')[1];
    return sub ? sub.replace(/[^a-z0-9]/gi, '') : 'bin';
  }

  // TEMPORARY — writes DEBUG_WATCH_JIDS hits to a durable file (not just console/pino),
  // since the worker's stdout isn't captured anywhere persistent. See DEBUG_WATCH_JIDS above.
  _debugWatchLog(sessionId, event, msg, extra = {}) {
    try {
      const filePath = path.join(this.messageLogger.logsDir, 'debug-watch.ndjson');
      const line = { ts: new Date().toISOString(), sessionId, event, ...extra, rawMsg: msg };
      fs.appendFileSync(filePath, JSON.stringify(line) + '\n', 'utf8');
    } catch { /* swallow — debug tap must never crash the pipeline */ }
    this.logger.warn({ sessionId, event }, 'DEBUG WATCH: hit for tracked contact — see debug-watch.ndjson');
  }

  // Builds the logger passed to makeWASocket. Uses pino's `hooks.logMethod` to inspect
  // every line Baileys logs internally — NOT by wrapping the destination stream (that
  // was the previous attempt: a plain object missing methods real pino destinations
  // require — flushSync, flush, on, reopen, end, destroy — which broke the logging
  // pipeline and hung live sessions). `hooks.logMethod` is a documented pino extension
  // point that intercepts the log call itself, before formatting/writing; the real
  // destination stream (pino.destination(...)) is passed through completely untouched.
  // Verified safe in isolation (a standalone script exercising normal/error calls and a
  // deliberately-thrown bug inside the hook) before being wired in here.
  _createBaileysLogger(sessionId, filePath) {
    const self = this;
    return pino(
      {
        level: 'warn',
        hooks: {
          logMethod(args, method, level) {
            // Never let an inspection bug take the actual log call down with it —
            // this is exactly the failure mode the previous destination-wrapping
            // attempt caused, just guarded against directly this time.
            try {
              self._inspectBaileysLogArgs(sessionId, args, level);
            } catch (err) {
              self.logger.debug({ sessionId, err: err.message }, 'Baileys log inspection failed (log call unaffected)');
            }
            return method.apply(this, args);
          },
        },
      },
      pino.destination(filePath),
    );
  }

  _inspectBaileysLogArgs(sessionId, args, level) {
    // pino log calls are typically (mergingObject, msg) or (msg); msg can also live on
    // the merging object depending on how the caller invoked it. Check both.
    const obj = (args[0] && typeof args[0] === 'object') ? args[0] : null;
    const msg = (typeof args[0] === 'string') ? args[0] : (obj?.msg || (typeof args[1] === 'string' ? args[1] : ''));
    if (!msg) return;

    // A message WhatsApp keeps asking us to resend, that our own send path can't
    // fulfill — every repeat costs a real assertSessions() round-trip to WhatsApp's
    // servers before it crashes in relayMessage (verified by reading Baileys' own
    // source, not guessed). Recorded separately from the generic alert below so
    // future repeats of the SAME message can be short-circuited via getMessage().
    if (msg === 'error in sending message again' && obj?.key && Array.isArray(obj.ids)) {
      this._recordStuckReceipt(sessionId, obj);
    }

    const ERROR_LEVEL = 50;
    let alertType = null;
    let kind = null; // 'decrypt' | 'handshake' | null
    if (msg.includes('failed to decrypt message')) {
      alertType = 'decrypt_failure';
      kind = 'decrypt';
    } else if (msg.includes("unexpected error in 'init queries'")) {
      alertType = 'handshake_timeout';
      kind = 'handshake';
    } else if (level >= ERROR_LEVEL) {
      // Catch-all: an error-level Baileys log we don't have a specific pattern for yet.
      // Still worth a structured alert instead of only living in the raw file — this is
      // exactly how the two patterns above were originally found, by manually grepping.
      alertType = 'other';
    } else {
      return; // warn-level, no known pattern — too noisy to alert on individually
    }

    // Every occurrence gets its own alert immediately — never thresholded/batched, so
    // "a decrypt error should not fail silently" holds from the very first occurrence.
    this.djangoClient.sendWorkerAlert(sessionId, {
      alert_type: alertType,
      severity: 'error',
      message: msg,
      context: obj ? this._safeAlertContext(obj) : null,
    });

    if (!kind) return;

    // Session-level escalation on top of the per-occurrence alerts above — see the
    // threshold constants' comment for why this is a separate, higher-bar signal.
    const session = this.sessions.get(sessionId);
    if (!session || session.connectionUnhealthy) return;

    if (kind === 'decrypt') session.consecutiveDecryptFailures++;
    else session.consecutiveInitQueryTimeouts++;

    const decryptTripped = session.consecutiveDecryptFailures >= DECRYPT_FAILURE_UNHEALTHY_THRESHOLD;
    const timeoutTripped = session.consecutiveInitQueryTimeouts >= INIT_QUERY_TIMEOUT_UNHEALTHY_THRESHOLD;
    if (!decryptTripped && !timeoutTripped) return;

    session.connectionUnhealthy = true;
    const reason = decryptTripped
      ? `Repeated message-decryption failures (${session.consecutiveDecryptFailures} since the last ` +
        `successful message) — this session's encryption keys are likely out of sync. Re-linking ` +
        `(disconnect, then scan a fresh QR code) usually resolves this; reconnecting alone won't, ` +
        `since it reuses the same key state.`
      : `Repeated connection setup timeouts (${session.consecutiveInitQueryTimeouts} since the last ` +
        `successful message) — WhatsApp isn't completing the post-connect handshake for this session. ` +
        `Re-linking (disconnect, then scan a fresh QR code) may resolve this.`;

    this.logger.error({ sessionId, reason }, 'Session marked connection_unhealthy');
    this.djangoClient.sendSessionStatus(sessionId, {
      status: session.status,
      connection_unhealthy: true,
      connection_unhealthy_reason: reason,
    });
  }

  // obj is the merging object from the 'error in sending message again' log call —
  // { key: { remoteJid, id: '', fromMe, participant }, ids: [...], trace }. remoteJid
  // on that key is frequently absent for this exact self-sync scenario (Baileys builds
  // it from attrs.recipient, which isn't always set for a fromMe-with-no-recipient
  // node) — fall back to participant, which is reliably present, so the dedup key
  // Django uses stays stable across repeats of the same stuck message.
  _recordStuckReceipt(sessionId, obj) {
    const session = this.sessions.get(sessionId);
    if (!session) return;

    const remoteJid = obj.key.remoteJid || obj.key.participant || 'unknown';
    for (const id of obj.ids) {
      if (id) session.knownStuckMessageIds.add(`${remoteJid}:${id}`);
    }

    this.djangoClient.sendStuckReceipt(sessionId, {
      remote_jid: remoteJid,
      participant: obj.key.participant || '',
      message_id: obj.ids[0] || '',
      from_me: !!obj.key.fromMe,
      context: this._safeAlertContext(obj),
    });
  }

  // Baileys' log objects can carry circular structures (sockets, streams) — JSON-safe
  // subset only, so the alert POST body itself can never be the next thing that throws.
  _safeAlertContext(obj) {
    try {
      return JSON.parse(JSON.stringify(obj));
    } catch {
      return { unserializable: true };
    }
  }

  // Called after any successfully-forwarded live message or history batch — proof the
  // session is actually working. Resets the failure counters, and if the session was
  // previously flagged unhealthy, reports the recovery so a transient issue that
  // self-heals doesn't leave a stale "needs re-link" banner up in the UI forever.
  _recordHealthySignal(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    const wasUnhealthy = session.connectionUnhealthy;
    session.consecutiveDecryptFailures = 0;
    session.consecutiveInitQueryTimeouts = 0;
    if (!wasUnhealthy) return;

    session.connectionUnhealthy = false;
    this.logger.info({ sessionId }, 'Session recovered — clearing connection_unhealthy');
    this.djangoClient.sendSessionStatus(sessionId, {
      status: session.status,
      connection_unhealthy: false,
      connection_unhealthy_reason: '',
    });
  }

  // ─── Public API ────────────────────────────────────────────────────────────

  async initialize() {
    if (!fs.existsSync(this.sessionStorePath)) return;
    const entries = fs.readdirSync(this.sessionStorePath, { withFileTypes: true });
    const sessionIds = entries.filter(e => e.isDirectory()).map(e => e.name);
    this.logger.info({ count: sessionIds.length }, 'Auto-restoring sessions from disk');
    for (const sessionId of sessionIds) {
      const credsFile = path.join(this.sessionStorePath, sessionId, 'creds.json');
      if (!fs.existsSync(credsFile)) {
        this.logger.info({ sessionId }, 'Skipping session — no credentials on disk (was logged out)');
        continue;
      }
      this.logger.info({ sessionId }, 'Restoring session');
      // Fetch account settings from Django so idle-disconnect and history rules are respected
      const options = await this.djangoClient.getAccountSettings(sessionId);
      // Seed the LID/username → phone cache from already-known contacts so messages
      // from them don't get dropped as unresolvable_lid while the cache is cold.
      const { lidToPhone, usernameToPhone } = await this.djangoClient.getLidMappings(sessionId);
      await this.createSession(sessionId, { ...options, lidToPhone, usernameToPhone });
    }
  }

  async createSession(sessionId, options = {}) {
    const existing = this.sessions.get(sessionId);
    if (existing?.sock) {
      return this._snapshot(sessionId);
    }

    if (existing?.status === SESSION_STATUS.LOGGED_OUT) {
      const authDir = path.join(this.sessionStorePath, sessionId);
      if (fs.existsSync(authDir)) {
        fs.rmSync(authDir, { recursive: true });
        this.logger.info({ sessionId }, 'Cleared logged-out credentials — fresh QR will be generated');
      }
    }

    this.sessions.set(sessionId, {
      sock: null,
      status: SESSION_STATUS.PENDING_QR,
      qrDataUrl: null,
      phoneNumber: null,
      displayName: null,
      // Sync settings
      syncHistory: options.sync_history !== false,
      historyDays: options.history_days || null,
      // Media auto-download (default on)
      autoDownloadMedia: options.auto_download_media !== false,
      // Idle disconnect (0 = disabled)
      idleDisconnectMs: options.idle_disconnect_minutes
        ? options.idle_disconnect_minutes * 60 * 1000
        : 0,
      lastActivityAt: Date.now(),
      idleTimer: null,
      preventReconnect: false,
      watchdogTimer: null,
      watchdogFired: false,
      lastError: null,
      // Consecutive failed-reconnect count, reset to 0 on every successful 'open'.
      // Drives exponential backoff below — hammering WhatsApp's servers with a flat
      // retry interval during an outage is exactly the kind of behavior that gets a
      // linked device flagged/rate-limited, forcing an unwanted fresh QR re-link.
      reconnectAttempts: 0,
      // LID → phone JID mapping built from contacts.set/upsert, seeded from
      // already-known contacts on restore (see initialize()) so the cache
      // isn't cold immediately after a worker restart.
      // Used to normalise outbound LID chat_ids (which have no senderPn).
      lidToPhone: { ...(options.lidToPhone || {}) },
      // username (bare handle, no @domain) → full phone JID.
      // Populated from contacts.set when c.username is present, also seeded on restore.
      // Used to resolve username-keyed chat JIDs once WhatsApp usernames roll out.
      usernameToPhone: { ...(options.usernameToPhone || {}) },
      // Health tracking (see _recordHealthySignal below). No detection call site sets
      // these true right now — see the NOTE near _recordHealthySignal's definition.
      consecutiveDecryptFailures: 0,
      consecutiveInitQueryTimeouts: 0,
      connectionUnhealthy: false,
      // Messages WhatsApp keeps asking us to resend that our own send path can't
      // fulfill (Baileys' relayMessage throws on them every time) — see
      // _recordStuckReceipt. getMessage() below returns null for anything in here
      // instead of the usual stub, so Baileys takes its own documented "message not
      // available" path instead of attempting (and failing) the resend again. Reset
      // on every process restart — a fresh process re-learns these the first time
      // WhatsApp asks again, which costs one crash, already-safely-caught by Baileys.
      knownStuckMessageIds: new Set(),
    });
    await this.djangoClient.replayFallbackReports?.();
    await this._connect(sessionId);
    return this._snapshot(sessionId);
  }

  async softDisconnect(sessionId) {
    const s = this.sessions.get(sessionId);
    if (!s || !s.sock) return false;
    s.preventReconnect = true;
    if (s.idleTimer) { clearInterval(s.idleTimer); s.idleTimer = null; }
    s.sock.end(new Error('Manual soft disconnect'));
    return true;
  }

  getStatus(sessionId) {
    const s = this.sessions.get(sessionId);
    if (!s) return null;
    return this._snapshot(sessionId);
  }

  getQR(sessionId) {
    const s = this.sessions.get(sessionId);
    if (!s) return null;
    return s.qrDataUrl;
  }

  getLastError(sessionId) {
    const s = this.sessions.get(sessionId);
    return s?.lastError || null;
  }

  async getGroupMetadata(sessionId, groupJid) {
    const s = this.sessions.get(sessionId);
    if (!s?.sock) return null;
    return await s.sock.groupMetadata(groupJid);
  }

  // Fetch all groups the account participates in and push metadata to Django.
  // Returns the number of groups synced, or null if the session is not connected.
  async syncAllGroups(sessionId) {
    const s = this.sessions.get(sessionId);
    if (!s?.sock) return null;

    const allGroups = await s.sock.groupFetchAllParticipating();
    const groupList = Object.values(allGroups || {});
    this.logger.info({ sessionId, count: groupList.length }, 'syncAllGroups: pushing to Django');

    for (const meta of groupList) {
      if (!meta?.id) continue;
      const participants = (meta.participants || []).map(p => ({
        jid:  p.id,
        role: p.superAdmin ? 'superadmin' : p.admin ? 'admin' : 'member',
      }));
      await this.djangoClient.sendGroupUpdate(sessionId, {
        group_id:     meta.id,
        name:         meta.subject || '',
        description:  meta.desc    || '',
        owner_jid:    meta.owner   || '',
        is_community: !!(meta.isCommunity),
        community_id: meta.linkedParent || null,
        participants,
      });
      if (meta.id && meta.subject) this.groupNameCache.set(meta.id, meta.subject);
    }
    return groupList.length;
  }

  async disconnect(sessionId) {
    const s = this.sessions.get(sessionId);
    if (!s || !s.sock) return false;
    await s.sock.logout();
    return true;
  }

  listSessions() {
    return [...this.sessions.entries()].map(([id, s]) => ({
      sessionId: id,
      status: s.status,
      phoneNumber: s.phoneNumber,
      displayName: s.displayName,
    }));
  }

  // ─── Internals ──────────────────────────────────────────────────────────────

  // (Re)arms the stuck-connection watchdog. Called on connect and every time a
  // connection.update event fires, so a healthy handshake or a legitimate QR refresh
  // keeps pushing the deadline out — only a socket that goes fully silent trips it.
  _armWatchdog(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    this._clearWatchdog(session);
    session.watchdogTimer = setTimeout(() => this._handleStuckConnection(sessionId), WATCHDOG_TIMEOUT_MS);
  }

  _clearWatchdog(session) {
    if (session?.watchdogTimer) {
      clearTimeout(session.watchdogTimer);
      session.watchdogTimer = null;
    }
  }

  // Fires when a session has gone silent for WATCHDOG_TIMEOUT_MS — no qr/open/close
  // event at all. Without this, a stalled handshake (bad network, stuck WebSocket,
  // corrupted auth state) leaves the session stuck in pending_qr/qr_generated forever
  // with no error ever surfacing to the UI.
  _handleStuckConnection(sessionId) {
    const session = this.sessions.get(sessionId);
    if (!session || session.status === SESSION_STATUS.CONNECTED) return;

    this.logger.error({ sessionId }, 'Connection watchdog fired — no response from WhatsApp servers, marking session as error');

    const deadSock = session.sock;
    session.watchdogFired = true;
    session.preventReconnect = true;
    session.status = SESSION_STATUS.ERROR;
    session.lastError = 'No response from WhatsApp servers — connection timed out. Please try again.';
    session.qrDataUrl = null;
    session.sock = null;

    this.djangoClient.sendSessionStatus(sessionId, { status: SESSION_STATUS.ERROR });

    try {
      deadSock?.end(new Error('Watchdog timeout — no connection event received'));
    } catch (_) {
      // Socket was never fully established — nothing to tear down.
    }
  }

  async _connect(sessionId) {
    const session = this.sessions.get(sessionId);

    // Auth-state load, version fetch, and socket construction all happen before any
    // connection.update event can fire — the watchdog (armed just below, once we have
    // a sock) can't catch a failure here. Without this try/catch, a corrupted
    // creds.json or a failed fetchLatestBaileysVersion() call would throw out of
    // createSession() and leave the session stuck at pending_qr with no sock and no
    // watchdog forever — the same silent hang, just triggered earlier.
    let sock;
    try {
      const authDir = path.join(this.sessionStorePath, sessionId);
      fs.mkdirSync(authDir, { recursive: true });

      const { state, saveCreds } = await useMultiFileAuthState(authDir);
      const { version } = await fetchLatestBaileysVersion();

      // Baileys' own internal logger — routed to a durable file (Baileys errors before
      // ever emitting messages.upsert, e.g. a decrypt failure, are otherwise invisible:
      // our own event handlers never fire for a message that never arrives). Also feeds
      // _inspectBaileysLogArgs via hooks.logMethod, which turns known failure patterns
      // (decrypt failures, handshake timeouts) into structured WorkerAlert records
      // instead of only living in this raw file.
      const baileysDebugLogger = this._createBaileysLogger(
        sessionId,
        path.join(this.messageLogger.logsDir, 'baileys-internal.log'),
      );

      sock = makeWASocket({
        version,
        auth: {
          creds: state.creds,
          keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })),
        },
        printQRInTerminal: false,
        logger: baileysDebugLogger,
        shouldIgnoreJid: jid => isJidBroadcast(jid),
        // Only request full (all-time) history when no day limit is set.
        // With a finite history_days window, recent sync is sufficient and far faster —
        // WhatsApp sends years of CDN blobs for full sync which can take hours.
        syncFullHistory: session.syncHistory && !session.historyDays,
        // Returning null (Baileys' own documented "message not available" path) for a
        // key already recorded by _recordStuckReceipt skips relayMessage entirely for
        // that repeat instead of attempting — and failing — the same resend again.
        // Every other key keeps the placeholder stub, unchanged from before. Must use
        // the exact same remoteJid-or-participant fallback _recordStuckReceipt used to
        // build the key, since Baileys passes this same (frequently remoteJid-less) key
        // shape into both places — a mismatched fallback here would mean the skip-list
        // never actually matches anything.
        getMessage: async (key) => {
          const jidKey = key.remoteJid || key.participant || 'unknown';
          if (session.knownStuckMessageIds.has(`${jidKey}:${key.id}`)) return null;
          return { conversation: '' };
        },
      });

      sock.ev.on('creds.update', saveCreds);
    } catch (err) {
      this.logger.error({ sessionId, error: err.message }, 'Failed to initialize connection');
      session.sock = null;
      session.status = SESSION_STATUS.ERROR;
      session.lastError = `Failed to start session: ${err.message}`;
      session.qrDataUrl = null;
      await this.djangoClient.sendSessionStatus(sessionId, { status: SESSION_STATUS.ERROR });
      return;
    }

    session.sock = sock;
    session.watchdogFired = false;
    this._armWatchdog(sessionId);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        session.qrDataUrl = await QRCode.toDataURL(qr);
        session.status = SESSION_STATUS.QR_GENERATED;
        this._armWatchdog(sessionId);
        this.logger.info({ sessionId }, 'QR generated');
        await this.djangoClient.sendSessionStatus(sessionId, {
          status: SESSION_STATUS.QR_GENERATED,
        });
      }

      if (connection === 'open') {
        this._clearWatchdog(session);
        const me = sock.user;
        session.status = SESSION_STATUS.CONNECTED;
        session.phoneNumber = me?.id?.split(':')[0] || null;
        session.displayName = me?.name || null;
        session.qrDataUrl = null;
        session.lastActivityAt = Date.now();
        session.reconnectAttempts = 0;
        // A fresh socket starts with a clean slate — don't carry over failure counts
        // from whatever this session was doing before this connect cycle. Always send
        // the clear to Django unconditionally (not gated on the in-memory session's
        // prior connectionUnhealthy value) — connection_unhealthy is persisted server
        // side, and a re-link (disconnect + fresh QR scan) creates a brand-new in-memory
        // session that never "was unhealthy" even though Django's stale flag from the
        // old session is still true. Gating on local memory left that flag — and its
        // banner — stuck forever after every re-link.
        session.consecutiveDecryptFailures = 0;
        session.consecutiveInitQueryTimeouts = 0;
        session.connectionUnhealthy = false;
        this.logger.info({ sessionId, phone: session.phoneNumber }, 'Session connected');
        await this.djangoClient.sendSessionStatus(sessionId, {
          status: SESSION_STATUS.CONNECTED,
          phone_number: session.phoneNumber,
          display_name: session.displayName,
          connection_unhealthy: false,
          connection_unhealthy_reason: '',
        });

        // Start idle disconnect timer if configured
        if (session.idleDisconnectMs > 0) {
          session.idleTimer = setInterval(async () => {
            const s = this.sessions.get(sessionId);
            if (!s || !s.sock) { clearInterval(session.idleTimer); return; }
            const idleMs = Date.now() - (s.lastActivityAt || Date.now());
            if (idleMs >= s.idleDisconnectMs) {
              this.logger.info(
                { sessionId, idleMinutes: Math.round(idleMs / 60000) },
                'Idle timeout — soft-disconnecting',
              );
              clearInterval(session.idleTimer);
              session.idleTimer = null;
              await this.softDisconnect(sessionId);
            }
          }, 60 * 1000);
        }
      }

      if (connection === 'close') {
        const code = lastDisconnect?.error?.output?.statusCode;
        const loggedOut = code === DisconnectReason.loggedOut;

        if (session.idleTimer) { clearInterval(session.idleTimer); session.idleTimer = null; }
        this._clearWatchdog(session);

        if (session.watchdogFired) {
          // Status/error/sock were already set by the watchdog — this close event is
          // just the dead socket unwinding. Don't overwrite the error state or reconnect.
          session.watchdogFired = false;
          session.preventReconnect = false;
          this.logger.info({ sessionId }, 'Watchdog-closed socket cleanup complete');
          return;
        }

        session.status = loggedOut ? SESSION_STATUS.LOGGED_OUT : SESSION_STATUS.DISCONNECTED;
        session.sock = null;
        this.logger.info({ sessionId, code, loggedOut }, 'Session closed');

        if (loggedOut) {
          // Delete credentials right now — don't defer this to the next createSession()
          // call. That deferred check only fires if this same in-memory session entry
          // is still around, which breaks the moment the worker process restarts (crash,
          // deploy, dev-server reload) before the account reconnects: initialize() rebuilds
          // an empty sessions Map and finds creds.json still on disk, so it reconnects with
          // credentials WhatsApp has already revoked. Baileys can still locally report
          // 'connected' in that case — producing a session that looks live in the UI but
          // never receives anything again (no history sync, no live messages), forever.
          const authDir = path.join(this.sessionStorePath, sessionId);
          if (fs.existsSync(authDir)) {
            try {
              fs.rmSync(authDir, { recursive: true });
              this.logger.info({ sessionId }, 'Logged out — cleared credentials immediately, fresh QR required');
            } catch (err) {
              this.logger.error({ sessionId, err: err.message }, 'Failed to clear logged-out credentials');
            }
          }
        }

        await this.djangoClient.sendSessionStatus(sessionId, {
          status: session.status,
        });

        if (!loggedOut) {
          if (session.preventReconnect) {
            session.preventReconnect = false;
            this.logger.info({ sessionId }, 'Soft disconnect — staying offline');
          } else {
            const attempt = session.reconnectAttempts++;
            const delayMs = Math.min(
              RECONNECT_BASE_DELAY_MS * 2 ** attempt,
              RECONNECT_MAX_DELAY_MS,
            );
            this.logger.info({ sessionId, attempt, delayMs }, `Reconnecting in ${Math.round(delayMs / 1000)}s`);
            setTimeout(() => this._connect(sessionId), delayMs);
          }
        }
      }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      session.lastActivityAt = Date.now();

      // TEMPORARY debug tap — see DEBUG_WATCH_JIDS above. Runs before any filtering
      // so it catches the event no matter what happens to it afterward.
      for (const m of messages) {
        if (_isDebugWatchTarget(m)) {
          let safeMsg = null;
          try { safeMsg = JSON.parse(JSON.stringify(m)); } catch { safeMsg = { unserializable: true }; }
          this._debugWatchLog(sessionId, 'messages.upsert', safeMsg, { type });
        }
      }

      // 'prepend' arrives when WhatsApp delivers missed messages after a reconnect.
      // Route those through the history batch path (no media download, deduped by Django).
      if (type === 'prepend') {
        const valid = [];
        for (const m of messages) {
          if (m.key?.remoteJid && m.message) {
            valid.push(m);
          } else {
            this._reportDropped(sessionId, m, 'prepend_no_content');
          }
        }
        if (valid.length) {
          this.logger.info({ sessionId, count: valid.length }, 'messages.upsert prepend — routing as history');
          await this._forwardHistoryBatch(sessionId, valid);
        }
        return;
      }

      if (type !== 'notify' && type !== 'append') {
        // Previously a silent debug-level log (invisible at the default LOG_LEVEL=info) with
        // no DB trace at all — messages hitting this path vanished with zero evidence anywhere.
        // Report each one explicitly so it shows up in whatsapp_dropped_message.
        this.logger.warn({ sessionId, type, count: messages.length }, 'messages.upsert — unhandled type, reporting as dropped');
        for (const m of messages) {
          this._reportDropped(sessionId, m, `unhandled_type:${type}`);
        }
        return;
      }

      for (const msg of messages) {
        // Log every incoming event so drops are traceable (before any filter)
        this.logger.debug(
          { sessionId, type, msgId: msg.key?.id, jid: msg.key?.remoteJid, hasMsg: !!msg.message },
          'messages.upsert received',
        );
        if (!msg.key?.remoteJid) {
          this._reportDropped(sessionId, msg, 'no_remote_jid');
          continue;
        }
        if (!msg.message) {
          this._reportDropped(sessionId, msg, 'no_message_content');
          continue;
        }
        await this._forwardMessage(sessionId, msg);
      }
    });

    sock.ev.on('messaging-history.set', async ({ messages, isLatest }) => {
      // TEMPORARY debug tap — see DEBUG_WATCH_JIDS above.
      for (const m of messages) {
        if (_isDebugWatchTarget(m)) {
          let safeMsg = null;
          try { safeMsg = JSON.parse(JSON.stringify(m)); } catch { safeMsg = { unserializable: true }; }
          this._debugWatchLog(sessionId, 'messaging-history.set', safeMsg);
        }
      }

      let filtered = messages.filter(m => m.key?.remoteJid && m.message);

      if (session.historyDays) {
        const cutoffMs = Date.now() - session.historyDays * 24 * 60 * 60 * 1000;
        filtered = filtered.filter(m => Number(m.messageTimestamp) * 1000 >= cutoffMs);
      }

      this.logger.info(
        { sessionId, received: messages.length, processing: filtered.length, isLatest },
        'History sync',
      );
      await this._forwardHistoryBatch(sessionId, filtered, { isLatest, received: messages.length });
    });

    // Sync contact names whenever Baileys provides them.
    // contacts.set fires on initial connect with the full contacts list.
    // contacts.upsert fires when individual contacts are updated.
    const _sendNamedContacts = async (contacts) => {
      // Build phone JID → alias mappings from contacts that expose LID and/or username.
      // e.g. { id: '923001234567@s.whatsapp.net', lid: '18806883308705@lid', username: 'mia.business', notify: 'Mia' }
      // Populate session caches used by _buildPayload for real-time alias resolution.
      const phoneToLid      = {};
      const phoneToUsername = {};
      const sess = this.sessions.get(sessionId);
      for (const c of contacts || []) {
        if (!c.id?.endsWith('@s.whatsapp.net')) continue;
        try {
          const phoneJid = jidNormalizedUser(c.id);
          if (c.lid) {
            const lidJid = jidNormalizedUser(c.lid);
            phoneToLid[phoneJid] = lidJid;
            if (sess) sess.lidToPhone[lidJid] = phoneJid;
          }
          // TODO(baileys-username ~Jul 2026): confirm field name once Baileys ships username support.
          // Assumed: c.username contains the bare handle (e.g. 'ahmed.mobile', no @ or domain).
          if (c.username) {
            const handle = c.username.toLowerCase().trim();
            phoneToUsername[phoneJid] = handle;
            if (sess) sess.usernameToPhone[handle] = phoneJid;
          }
        } catch { /* skip malformed entry */ }
      }

      const batch = [];
      for (const c of contacts || []) {
        const name = c.name || c.notify || c.verifiedName || '';
        if (!name) continue;

        // Pure LID entries are aliases for phone contacts — they carry no identity of their
        // own and must never be created as primary contacts in Django.
        if (c.id?.endsWith('@lid')) continue;

        // jidNormalizedUser can throw on a malformed id — this used to sit outside any
        // try/catch, so one bad contact entry aborted this whole loop and every OTHER
        // contact's alias mapping in the same contacts.set/upsert batch was silently
        // lost with it (no log, no trace). Skip just the malformed one instead.
        try {
          const wa_contact_id = jidNormalizedUser(c.id);
          if (!wa_contact_id) continue;

          const phone_number = c.id?.endsWith('@s.whatsapp.net') ? c.id.split('@')[0] : '';
          const lid_jid  = phoneToLid[wa_contact_id]      || null;
          const username = phoneToUsername[wa_contact_id]  || null;

          batch.push({ wa_contact_id, push_name: name, phone_number, lid_jid, username });
        } catch (err) {
          this.logger.warn({ sessionId, contactId: c.id, err: err.message }, 'Skipping malformed contact entry');
        }
      }

      const validBatch = batch.filter(c => c.wa_contact_id && c.push_name);
      if (!validBatch.length) return;

      // Send in chunks of 100 to avoid oversized payloads
      for (let i = 0; i < validBatch.length; i += 100) {
        await this.djangoClient.sendContactsUpdate(sessionId, validBatch.slice(i, i + 100));
      }
    };

    sock.ev.on('contacts.set', async ({ contacts }) => {
      const lidCount      = (contacts || []).filter(c => c.id?.endsWith('@lid')).length;
      const lidMappable   = (contacts || []).filter(c => c.id?.endsWith('@s.whatsapp.net') && c.lid).length;
      const usernameMapped = (contacts || []).filter(c => c.id?.endsWith('@s.whatsapp.net') && c.username).length;
      this.logger.info(
        { sessionId, total: (contacts || []).length, lidContacts: lidCount, lidMappable, usernameMapped },
        'Contacts.set received',
      );
      await _sendNamedContacts(contacts);
    });

    sock.ev.on('contacts.upsert', async (contacts) => {
      await _sendNamedContacts(contacts);
    });

    // ── Group metadata sync ────────────────────────────────────────────────────
    // Build a normalized group payload from Baileys GroupMetadata and send to Django.
    const _sendGroupMetadata = async (meta) => {
      if (!meta?.id) return;
      const participants = (meta.participants || []).map(p => ({
        jid:  p.id,
        role: p.superAdmin ? 'superadmin' : p.admin ? 'admin' : 'member',
      }));
      await this.djangoClient.sendGroupUpdate(sessionId, {
        group_id:     meta.id,
        name:         meta.subject || '',
        description:  meta.desc    || '',
        owner_jid:    meta.owner   || '',
        is_community: !!(meta.isCommunity),
        community_id: meta.linkedParent || null,
        participants,
      });
    };

    // On initial connect: fetch all groups the account participates in and sync them all.
    // groupFetchAllParticipating() returns { [groupId]: GroupMetadata }.
    sock.ev.on('connection.update', async (update) => {
      if (update.connection !== 'open') return;
      try {
        const allGroups = await sock.groupFetchAllParticipating();
        const groupList = Object.values(allGroups || {});
        this.logger.info({ sessionId, count: groupList.length }, 'Syncing all group metadata on connect');
        for (const meta of groupList) {
          await _sendGroupMetadata(meta);
          // Also warm the name cache
          if (meta.id && meta.subject) this.groupNameCache.set(meta.id, meta.subject);
        }
      } catch (err) {
        this.logger.warn({ sessionId, error: err.message }, 'groupFetchAllParticipating failed');
      }
    });

    // Incremental group metadata updates (name/description changes, etc.)
    sock.ev.on('groups.update', async (updates) => {
      for (const update of updates || []) {
        if (!update.id) continue;
        try {
          // Fetch fresh metadata so we have the full participant list
          const meta = await sock.groupMetadata(update.id).catch(() => null);
          if (meta) {
            await _sendGroupMetadata(meta);
            if (meta.subject) this.groupNameCache.set(meta.id, meta.subject);
          } else {
            // Partial update only — send what we have without participants
            await this.djangoClient.sendGroupUpdate(sessionId, {
              group_id:    update.id,
              name:        update.subject        || undefined,
              description: update.desc           || undefined,
              owner_jid:   update.owner          || undefined,
              is_community: update.isCommunity   || undefined,
              community_id: update.linkedParent  || undefined,
            });
          }
        } catch (err) {
          this.logger.warn({ sessionId, groupId: update.id, error: err.message }, 'groups.update handling failed');
        }
      }
    });

    // Incremental participant changes (join, leave, promote, demote)
    sock.ev.on('group-participants.update', async ({ id, participants, action }) => {
      if (!id || !participants?.length) return;
      try {
        await this.djangoClient.sendGroupParticipantsUpdate(sessionId, id, action, participants);
      } catch (err) {
        this.logger.warn({ sessionId, groupId: id, action, error: err.message }, 'group-participants.update failed');
      }
    });
  }

  async _getGroupName(sock, jid) {
    if (this.groupNameCache.has(jid)) return this.groupNameCache.get(jid);
    try {
      const meta = await sock.groupMetadata(jid);
      const name = meta.subject || '';
      this.groupNameCache.set(jid, name);
      return name;
    } catch {
      return '';
    }
  }

  // Build a normalized payload + log-entry for a single Baileys message.
  // Returns null if the message should be filtered (protocol/system messages).
  // Pass isHistory:true to skip media download and mark the payload for the batch endpoint.
  async _buildPayload(sessionId, msg, { isHistory = false } = {}) {
    const _skip = (reason) => {
      this.logger.info({ sessionId, msgId: msg.key?.id, jid: msg.key?.remoteJid, reason }, '_buildPayload filtered');
      this._reportDropped(sessionId, msg, reason);
      return null;
    };
    if (msg.key.remoteJid === 'status@broadcast') return _skip('status@broadcast');
    if (msg.messageStubType) return _skip(`messageStubType:${msg.messageStubType}`);
    // Baileys message objects are protobuf class instances: every schema field exists as a
    // prototype getter even when not set, so `'protocolMessage' in msg.message` is always true.
    // Check the actual value instead — null/undefined means the field is unset (not a protocol msg).
    if (msg.message?.protocolMessage != null) {
      const pmType = msg.message.protocolMessage.type ?? 'unknown';
      return _skip(`protocolMessage:${pmType}`);
    }

    // Drop senderKeyDistributionMessage ONLY when it is the sole content of the envelope.
    // WhatsApp often bundles the key distribution with a real user message (text/media) in
    // a single envelope — dropping the whole envelope in that case silently loses the message.
    // Pure key envelopes (no other content besides optional messageContextInfo or protocolMessage)
    // are safe to drop.
    if (msg.message?.senderKeyDistributionMessage) {
      const METADATA_KEYS = new Set(['senderKeyDistributionMessage', 'messageContextInfo', 'protocolMessage']);
      const hasUserContent = Object.keys(msg.message).some(k => !METADATA_KEYS.has(k));
      if (!hasUserContent) return _skip('senderKeyDistributionMessage');
      // else: fall through — real content exists, let _parseMessage extract it
    }

    const rawJid = msg.key.remoteJid;
    const fromMe = msg.key.fromMe;

    const isLidJid = rawJid?.endsWith('@lid');
    // Username JIDs: @s.whatsapp.net but local part contains non-digit characters.
    // Phone JIDs are always pure digits (e.g. 971503218002@s.whatsapp.net).
    // Username JIDs will look like ahmed.mobile@s.whatsapp.net once the feature rolls out.
    const isUsernameJid = rawJid?.endsWith('@s.whatsapp.net')
      && !!rawJid && !/^\d+@/.test(rawJid);
    const senderPn = msg.key.senderPn;
    const session = this.sessions.get(sessionId);

    // Computed here (rather than after resolution, as before) because the LID
    // resolution block below may need to preserve this message's full content
    // as unresolved instead of dropping it — that requires the actual text/type/
    // timestamp/raw payload, not just msg.key. See _preserveUnresolvedMessage.
    const messageTimestamp = msg.messageTimestamp
      ? new Date(Number(msg.messageTimestamp) * 1000).toISOString()
      : new Date().toISOString();
    const { messageType, messageText, hasMedia, mediaMimeType } = this._parseMessage(msg);
    let safeRaw = null;
    try { safeRaw = JSON.parse(JSON.stringify(msg)); } catch { safeRaw = null; }
    const direction = (fromMe === true) ? 'outbound' : 'inbound';

    // Resolve alias JIDs → canonical phone JID so every contact has exactly one identity.
    //
    // LID priority (individual chat where remoteJid IS a LID):
    //   1. senderPn on inbound — Baileys' most reliable real-time resolution; cache it.
    //   2. session.lidToPhone  — built from contacts.set/upsert before any messages arrive,
    //      or from a prior hit on source 3 below.
    //   3. Django's persisted whatsapp_contact.lid_jid — a single-LID lookup, for exactly
    //      the case source 2 can't cover on its own: an outbound self-echo (fromMe:true)
    //      never carries senderPn, so it depends entirely on the in-memory cache already
    //      being warm — which goes cold on every worker restart if this LID's mapping
    //      hasn't been (re)learned yet this session. See
    //      'docs/Contact Message Loss — LID Resolution Fix Proposal.md' Fix 2.
    //   If none of the three resolve, the message is preserved as unresolved (NOT
    //   dropped) when it carries real content — see _preserveUnresolvedMessage.
    //
    // Username priority (individual chat where remoteJid has a non-digit local part):
    //   1. session.usernameToPhone — built from contacts.set when c.username is present.
    //   Drop 'unresolvable_username' if not in cache.
    //   TODO(baileys-username ~Jul 2026): Baileys may also expose msg.key.senderPn here
    //   (same field as LID resolution). Add that as priority-1 once confirmed and cache it.
    //
    // Group JIDs and normal phone JIDs are passed through unchanged. Note: an unresolvable
    // LID *group participant* (remoteJid is a real @g.us group; only the sender within it
    // is an unresolvable LID) is a different, narrower case handled separately below and
    // still hard-drops — that message's chat identity is already known, only scope for this
    // preservation pass was the chat-level LID case per the fix-proposal document.
    let resolvedChatJid = rawJid;
    if (isLidJid) {
      const rawLidJid = jidNormalizedUser(rawJid);
      if (!fromMe && senderPn) {
        const phoneJid = jidNormalizedUser(senderPn);
        session.lidToPhone[rawLidJid] = phoneJid;
        resolvedChatJid = phoneJid;
      } else if (session.lidToPhone[rawLidJid]) {
        resolvedChatJid = session.lidToPhone[rawLidJid];
      } else {
        let persistedPhoneJid = null;
        try {
          const result = await this.djangoClient.lookupLidMapping(sessionId, rawLidJid);
          if (result?.found && result.phone_jid) {
            const validated = jidNormalizedUser(result.phone_jid);
            if (validated?.endsWith('@s.whatsapp.net')) persistedPhoneJid = validated;
          }
        } catch (err) {
          // Explicit, logged failure — NOT treated as "not found" and NOT a reason to
          // guess. Falls through to preservation below exactly as a genuine miss would.
          this.logger.warn(
            { sessionId, msgId: msg.key?.id, rawLidJid, err: err.message },
            'lookupLidMapping failed — preserving message as unresolved instead of guessing',
          );
        }

        if (persistedPhoneJid) {
          session.lidToPhone[rawLidJid] = persistedPhoneJid;
          resolvedChatJid = persistedPhoneJid;
        } else {
          return await this._preserveUnresolvedMessage(sessionId, msg, {
            reason: 'unresolvable_lid',
            rawLidJid,
            fromMe,
            direction,
            messageType,
            messageText,
            hasMedia,
            mediaMimeType,
            messageTimestamp,
            safeRaw,
            isHistory,
          });
        }
      }
    } else if (isUsernameJid) {
      const handle = rawJid.split('@')[0].toLowerCase();
      const cached = session.usernameToPhone[handle];
      if (cached) {
        resolvedChatJid = cached;
      } else {
        // Cannot resolve username → phone. Drop loudly; do not create a username-keyed contact.
        // Once Baileys exposes senderPn for username chats, add real-time resolution above.
        return _skip('unresolvable_username');
      }
    }

    const chatId = jidNormalizedUser(resolvedChatJid);
    const isGroup = chatId?.endsWith('@g.us');

    // senderJid: who actually authored this message.
    //   Group (phone):  msg.key.participant (member's JID within the group)
    //   Group (LID):    msg.key.participantPn (Baileys resolves the real phone for us) + cache mapping
    //   Inbound LID:    senderPn (real phone number provided by Baileys)
    //   Inbound normal: remoteJid (the other party IS the sender)
    //   Outbound:       resolved chatId (placeholder — own JID not available here)
    let rawSenderJid;
    if (isGroup) {
      const participant = msg.key.participant || rawJid;
      const participantPn = msg.key.participantPn;
      if (participant?.endsWith('@lid')) {
        if (participantPn) {
          // Baileys provides real-time resolution — use it and cache for future messages.
          rawSenderJid = participantPn;
          const lidKey  = jidNormalizedUser(participant);
          const phoneVal = jidNormalizedUser(participantPn);
          if (lidKey && phoneVal) session.lidToPhone[lidKey] = phoneVal;
        } else {
          // No participantPn — try the session cache built from contacts.set.
          const lidKey = jidNormalizedUser(participant);
          const cached = session.lidToPhone[lidKey];
          if (cached) {
            rawSenderJid = cached;
          } else {
            // Completely unresolvable — drop loudly rather than creating a LID-keyed contact.
            return _skip('unresolvable_lid');
          }
        }
      } else if (participant?.endsWith('@s.whatsapp.net') && !/^\d+@/.test(participant)) {
        // Username-keyed group participant (non-digit local part on @s.whatsapp.net).
        // TODO(baileys-username ~Jul 2026): confirm whether msg.key.participantPn is provided
        // here (analogous to participantPn for LID participants). Until then, resolve via cache.
        const handle = participant.split('@')[0].toLowerCase();
        const cached = session.usernameToPhone[handle];
        if (cached) {
          rawSenderJid = cached;
        } else {
          return _skip('unresolvable_username');
        }
      } else {
        rawSenderJid = participant;
      }
    } else if (!fromMe && isLidJid && senderPn) {
      rawSenderJid = senderPn;
    } else {
      rawSenderJid = resolvedChatJid;
    }
    const senderJid = jidNormalizedUser(rawSenderJid);
    const senderNumber = senderJid?.split('@')[0] || '';

    const groupName = isGroup ? await this._getGroupName(session.sock, chatId) : '';

    // Media download is skipped for history messages — they are old and media may have
    // expired on WhatsApp servers. Only download for live (real-time) messages.
    let mediaUrl = null;
    if (hasMedia && !isHistory && session.autoDownloadMedia) {
      try {
        const buffer = await downloadMediaMessage(msg, 'buffer', {}, {
          logger: pino({ level: 'silent' }),
          reuploadRequest: session.sock.updateMediaMessage,
        });
        const ext = this._mimeToExt(mediaMimeType);
        const filename = `${msg.key.id}.${ext}`;
        const mediaDir = path.join(this.mediaStorePath, String(sessionId));
        fs.mkdirSync(mediaDir, { recursive: true });
        fs.writeFileSync(path.join(mediaDir, filename), buffer);
        mediaUrl = `/media/${sessionId}/${filename}`;
      } catch (err) {
        this.logger.warn({ sessionId, msgId: msg.key.id, err: err.message }, 'Media download failed — message saved without attachment');
      }
    }

    const payload = {
      worker_session_id: sessionId,
      provider_message_id: msg.key.id,
      chat_id: chatId,
      chat_type: isGroup ? 'group' : 'individual',
      sender_number: senderNumber,
      push_name: msg.pushName || '',
      group_name: groupName,
      direction,
      message_type: messageType,
      message_text: messageText,
      message_time: messageTimestamp,
      has_media: hasMedia,
      media_mime_type: mediaMimeType,
      media_url: mediaUrl,
      raw_payload: safeRaw,
      ...(isHistory ? { is_history: true } : {}),
    };

    const logEntry = {
      ts: new Date().toISOString(),
      session_id: sessionId,
      provider_message_id: msg.key.id,
      chat_id: chatId,
      chat_type: isGroup ? 'group' : 'individual',
      direction,
      message_type: messageType,
      message_text: (messageText || '').slice(0, 500),
      sender_number: senderNumber,
      push_name: msg.pushName || '',
      group_name: groupName,
      has_media: hasMedia,
      media_mime_type: mediaMimeType,
      raw_payload: safeRaw,
      forward_status: 'success',
      forward_error: null,
      ...(isHistory ? { is_history: true } : {}),
    };

    return { payload, logEntry };
  }

  // Durable preservation for a message that carries genuine user content but whose
  // chat-level LID couldn't be resolved to a phone JID by any of the three resolution
  // sources in _buildPayload. Identity resolution and message preservation are
  // separate concerns (see 'docs/Contact Message Loss — LID Resolution Fix
  // Proposal.md') — this is the "no" branch of that split, replacing what used to be
  // a hard _skip('unresolvable_lid') that discarded the message content entirely.
  //
  // Returns null either way, matching _skip's contract, so the call site in
  // _buildPayload can `return await this._preserveUnresolvedMessage(...)` exactly
  // like it previously did `return _skip(...)`.
  async _preserveUnresolvedMessage(sessionId, msg, opts) {
    const {
      reason, rawLidJid, fromMe, direction,
      messageType, messageText, hasMedia, mediaMimeType,
      messageTimestamp, safeRaw, isHistory,
    } = opts;

    // Same shape _buildPayload's normal payload uses, minus chat_id/chat identity
    // fields (unknown) — this is exactly what recover_unresolved_for_lid on the
    // Django side expects to be able to plug a resolved chat_id into later and feed
    // straight into the same ingestion path, without WhatsApp ever resending it.
    const recoverablePayload = {
      provider_message_id: msg.key?.id || null,
      chat_type: 'individual',
      sender_number: '',
      push_name: msg.pushName || '',
      group_name: '',
      direction,
      message_type: messageType,
      message_text: messageText,
      message_time: messageTimestamp,
      has_media: hasMedia,
      media_mime_type: mediaMimeType,
      media_url: null,
      raw_payload: safeRaw,
      ...(isHistory ? { is_history: true } : {}),
    };

    const unresolvedPayload = {
      provider_message_id: msg.key?.id || null,
      raw_jid: msg.key?.remoteJid || null,
      participant_jid: msg.key?.participant || '',
      lid_jid: rawLidJid || '',
      from_me: !!fromMe,
      direction,
      message_type: messageType,
      message_text: messageText,
      has_media: hasMedia,
      message_time: messageTimestamp,
      push_name: msg.pushName || '',
      is_history: !!isHistory,
      reason,
      raw_key: msg.key ? this._safeAlertContext(msg.key) : null,
      raw_payload: recoverablePayload,
    };

    this.logger.info(
      { sessionId, msgId: msg.key?.id, jid: msg.key?.remoteJid, reason },
      '_buildPayload unresolved — preserving content instead of dropping',
    );

    try {
      const result = await this.djangoClient.sendUnresolvedMessage(sessionId, unresolvedPayload);
      this.logger.warn(
        { sessionId, msgId: msg.key?.id, jid: msg.key?.remoteJid, reason, unresolvedId: result?.id },
        'Message preserved as unresolved (LID resolution failed)',
      );
    } catch (err) {
      // Persistence failure must be loud and explicit — never treated as though the
      // message were safely preserved, and deliberately NOT given a local-file
      // fallback (unlike sendDroppedMessage/sendWorkerAlert/sendStuckReceipt) per
      // the P0 spec: a second silent source of truth for the core message path is
      // exactly the failure mode this whole change exists to eliminate.
      this.logger.error(
        { sessionId, msgId: msg.key?.id, jid: msg.key?.remoteJid, reason, err: err.message },
        'Failed to preserve unresolved message — content may be lost',
      );
      try {
        await this.djangoClient.sendWorkerAlert(sessionId, {
          alert_type: 'unresolved_message_failed',
          severity: 'error',
          message: `Failed to persist unresolved message: ${err.message}`,
          context: {
            operation: 'sendUnresolvedMessage',
            msgId: msg.key?.id || null,
            rawJid: msg.key?.remoteJid || null,
            lidJid: rawLidJid || null,
            reason,
            error: err.message,
          },
        });
      } catch (alertErr) {
        // sendWorkerAlert already has its own internal try/catch + local-file
        // fallback (see django-client.js) — this outer catch only guards against
        // that call itself throwing synchronously before reaching its own guard.
        this.logger.error(
          { sessionId, msgId: msg.key?.id, err: alertErr.message },
          'Failed to even alert on unresolved-message persistence failure',
        );
      }
    }

    return null;
  }

  async _reportDropped(sessionId, msg, reason) {
    this.logger.info(
      { sessionId, msgId: msg.key?.id, jid: msg.key?.remoteJid, hasMsg: !!msg.message, reason },
      'message dropped before Django',
    );
    // Fire-and-forget — don't await so the upsert loop is never blocked by HTTP
    this.djangoClient.sendDroppedMessage(sessionId, {
      msg_id: msg.key?.id || null,
      raw_jid: msg.key?.remoteJid || null,
      from_me: msg.key?.fromMe ?? null,
      has_message: !!msg.message,
      reason,
      // Merge the message field names into raw_key so the UI can show
      // whether a senderKeyDistributionMessage drop was a pure key envelope
      // (only _msgKeys: ['senderKeyDistributionMessage']) or a combined one.
      raw_key: msg.key
        ? { ...msg.key, _msgKeys: Object.keys(msg.message || {}) }
        : null,
    });
  }

  async _forwardMessage(sessionId, msg) {
    // Phase 1: build payload — _skip() already calls _reportDropped for filtered messages
    let built;
    try {
      built = await this._buildPayload(sessionId, msg);
    } catch (err) {
      this.logger.error({ sessionId, msgId: msg.key?.id, err: err.message }, '_buildPayload threw unexpectedly');
      this._reportDropped(sessionId, msg, 'build_error');
      return;
    }
    if (!built) return;

    // Phase 2: forward to Django
    const { payload, logEntry } = built;
    try {
      await this.djangoClient.sendMessageIngest(payload);
      this._recordHealthySignal(sessionId);
    } catch (fwdErr) {
      logEntry.forward_status = 'error';
      logEntry.forward_error  = fwdErr.message;
      this.logger.error({ sessionId, msgId: msg.key?.id, err: fwdErr.message }, 'Failed to forward message to Django');
      this._reportDropped(sessionId, msg, 'forward_failed');
    } finally {
      this.messageLogger.write(sessionId, logEntry);
    }
  }

  async _forwardHistoryBatch(sessionId, msgs, { isLatest = false, received = msgs.length } = {}) {
    const CHUNK_SIZE = 100;

    // Build all payloads (filters protocol messages; fetches group names via cache).
    // A build failure here is reported the same way as the live path (_reportDropped)
    // instead of only a raw logger.warn — this function also carries reconnect-
    // redelivered LIVE messages via the 'prepend' branch above, so this same gap
    // silently dropped current messages too, not just historical ones.
    const built = [];
    for (const msg of msgs) {
      try {
        const result = await this._buildPayload(sessionId, msg, { isHistory: true });
        if (result) built.push(result);
      } catch (err) {
        this.logger.warn({ sessionId, msgId: msg.key?.id, err: err.message }, 'Failed to build history payload — skipping');
        this._reportDropped(sessionId, msg, 'history_build_error');
      }
    }

    if (!built.length) {
      // Still report this chunk to Django — even empty. A narrow history_days window
      // (or a chunk that's entirely older than it) can filter an entire WhatsApp-
      // delivered batch down to zero, and without this call the sync-progress UI never
      // sees a single history_sync log, making a *finished* sync indistinguishable from
      // one that's still hanging.
      try {
        await this.djangoClient.sendMessageIngestBatch(sessionId, [], { isLatest, received });
      } catch (err) {
        this.logger.error({ sessionId, err: err.message }, 'Failed to report empty history batch to Django');
      }
      return;
    }

    this.logger.info({ sessionId, total: built.length, chunks: Math.ceil(built.length / CHUNK_SIZE) }, 'Sending history batch to Django');

    for (let i = 0; i < built.length; i += CHUNK_SIZE) {
      const chunk = built.slice(i, i + CHUNK_SIZE);
      const payloads = chunk.map(b => b.payload);

      let forwardStatus = 'success';
      let forwardError = null;

      try {
        const result = await this.djangoClient.sendMessageIngestBatch(sessionId, payloads, { isLatest, received });
        this._recordHealthySignal(sessionId);
        // A non-throwing response can still report per-message failures (result.errors)
        // — Django returns 200 for the batch call itself even when some items inside it
        // failed to persist. Previously this branch treated ANY non-throw as total
        // success and marked every message in the chunk delivered, even ones Django
        // just told us it lost. Django already writes its own DroppedMessage rows and a
        // batch_partial_failure WorkerAlert for the aggregate — this just keeps the
        // worker's own local message log honest instead of contradicting that.
        if (result && result.errors > 0) {
          forwardStatus = 'partial_error';
          forwardError = `${result.errors} of ${result.total ?? payloads.length} messages in this batch failed to persist (see Django DroppedMessage/WorkerAlert)`;
          this.logger.warn(
            { sessionId, chunkIndex: Math.floor(i / CHUNK_SIZE), size: chunk.length, errors: result.errors },
            'History batch chunk had partial persistence failures',
          );
        }
      } catch (err) {
        forwardStatus = 'error';
        forwardError = err.message;
        this.logger.error(
          { sessionId, chunkIndex: Math.floor(i / CHUNK_SIZE), size: chunk.length, err: err.message },
          'History batch chunk failed',
        );
      }

      for (const { logEntry } of chunk) {
        logEntry.forward_status = forwardStatus;
        logEntry.forward_error  = forwardError;
        this.messageLogger.write(sessionId, logEntry);
      }
    }
  }

  _parseMessage(msg) {
    let m = msg.message || {};

    // Unwrap message containers — outbound messages sent from your own phone
    // are wrapped in deviceSentMessage; ephemeral/view-once have their own wrappers
    if (m.deviceSentMessage?.message) m = m.deviceSentMessage.message;
    if (m.ephemeralMessage?.message) m = m.ephemeralMessage.message;
    if (m.viewOnceMessage?.message) m = m.viewOnceMessage.message;
    if (m.viewOnceMessageV2?.message) m = m.viewOnceMessageV2.message;
    if (m.documentWithCaptionMessage?.message) m = m.documentWithCaptionMessage.message;
    if (m.editedMessage?.message) m = m.editedMessage.message;

    if (m.conversation || m.extendedTextMessage) {
      return {
        messageType: 'text',
        messageText: m.conversation || m.extendedTextMessage?.text || '',
        hasMedia: false,
        mediaMimeType: '',
      };
    }
    if (m.imageMessage) {
      return { messageType: 'image', messageText: m.imageMessage.caption || '', hasMedia: true, mediaMimeType: m.imageMessage.mimetype || '' };
    }
    if (m.videoMessage) {
      return { messageType: 'video', messageText: m.videoMessage.caption || '', hasMedia: true, mediaMimeType: m.videoMessage.mimetype || '' };
    }
    if (m.audioMessage) {
      return { messageType: 'audio', messageText: '', hasMedia: true, mediaMimeType: m.audioMessage.mimetype || '' };
    }
    if (m.documentMessage) {
      return { messageType: 'document', messageText: m.documentMessage.caption || '', hasMedia: true, mediaMimeType: m.documentMessage.mimetype || '' };
    }
    if (m.stickerMessage) {
      return { messageType: 'sticker', messageText: '', hasMedia: true, mediaMimeType: m.stickerMessage.mimetype || '' };
    }
    if (m.locationMessage) {
      return { messageType: 'location', messageText: '', hasMedia: false, mediaMimeType: '' };
    }
    if (m.contactMessage || m.contactsArrayMessage) {
      return { messageType: 'contact', messageText: '', hasMedia: false, mediaMimeType: '' };
    }

    return { messageType: 'unknown', messageText: '', hasMedia: false, mediaMimeType: '' };
  }

  _snapshot(sessionId) {
    const s = this.sessions.get(sessionId);
    if (!s) return null;
    return {
      sessionId,
      status: s.status,
      phoneNumber: s.phoneNumber,
      displayName: s.displayName,
      hasQR: !!s.qrDataUrl,
      lastError: s.lastError || null,
    };
  }
}

module.exports = { SessionManager, SESSION_STATUS };
