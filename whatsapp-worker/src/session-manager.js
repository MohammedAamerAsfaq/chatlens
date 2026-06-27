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
      await this.createSession(sessionId, options);
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
    });
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

  async getGroupMetadata(sessionId, groupJid) {
    const s = this.sessions.get(sessionId);
    if (!s?.sock) return null;
    return await s.sock.groupMetadata(groupJid);
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

  async _connect(sessionId) {
    const authDir = path.join(this.sessionStorePath, sessionId);
    fs.mkdirSync(authDir, { recursive: true });

    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    const { version } = await fetchLatestBaileysVersion();

    const session = this.sessions.get(sessionId);

    const sock = makeWASocket({
      version,
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })),
      },
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }),
      shouldIgnoreJid: jid => isJidBroadcast(jid),
      syncFullHistory: session.syncHistory,
      getMessage: async () => ({ conversation: '' }),
    });

    session.sock = sock;

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        session.qrDataUrl = await QRCode.toDataURL(qr);
        session.status = SESSION_STATUS.QR_GENERATED;
        this.logger.info({ sessionId }, 'QR generated');
        await this.djangoClient.sendSessionStatus(sessionId, {
          status: SESSION_STATUS.QR_GENERATED,
        });
      }

      if (connection === 'open') {
        const me = sock.user;
        session.status = SESSION_STATUS.CONNECTED;
        session.phoneNumber = me?.id?.split(':')[0] || null;
        session.displayName = me?.name || null;
        session.qrDataUrl = null;
        session.lastActivityAt = Date.now();
        this.logger.info({ sessionId, phone: session.phoneNumber }, 'Session connected');
        await this.djangoClient.sendSessionStatus(sessionId, {
          status: SESSION_STATUS.CONNECTED,
          phone_number: session.phoneNumber,
          display_name: session.displayName,
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

        session.status = loggedOut ? SESSION_STATUS.LOGGED_OUT : SESSION_STATUS.DISCONNECTED;
        session.sock = null;
        this.logger.info({ sessionId, code, loggedOut }, 'Session closed');

        await this.djangoClient.sendSessionStatus(sessionId, {
          status: session.status,
        });

        if (!loggedOut) {
          if (session.preventReconnect) {
            session.preventReconnect = false;
            this.logger.info({ sessionId }, 'Soft disconnect — staying offline');
          } else {
            this.logger.info({ sessionId }, 'Reconnecting in 5s');
            setTimeout(() => this._connect(sessionId), 5000);
          }
        }
      }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify' && type !== 'append') return;
      session.lastActivityAt = Date.now();
      for (const msg of messages) {
        if (!msg.key?.remoteJid) continue;
        if (!msg.message) continue;
        await this._forwardMessage(sessionId, msg);
      }
    });

    sock.ev.on('messaging-history.set', async ({ messages, isLatest }) => {
      let filtered = messages.filter(m => m.key?.remoteJid && m.message);

      if (session.historyDays) {
        const cutoffMs = Date.now() - session.historyDays * 24 * 60 * 60 * 1000;
        filtered = filtered.filter(m => Number(m.messageTimestamp) * 1000 >= cutoffMs);
      }

      this.logger.info(
        { sessionId, received: messages.length, processing: filtered.length, isLatest },
        'History sync',
      );
      await this._forwardHistoryBatch(sessionId, filtered);
    });

    // Sync contact names whenever Baileys provides them.
    // contacts.set fires on initial connect with the full contacts list.
    // contacts.upsert fires when individual contacts are updated.
    const _sendNamedContacts = async (contacts) => {
      // Build a LID→phone mapping from contacts that have both a phone JID and a lid field.
      // e.g. { id: '923001234567@s.whatsapp.net', lid: '18806883308705@lid', notify: 'Mia' }
      // tells us that '18806883308705@lid' maps to phone '923001234567'.
      const lidToPhone = {};
      const lidToPushName = {};
      for (const c of contacts || []) {
        if (c.id && c.id.endsWith('@s.whatsapp.net') && c.lid) {
          try {
            const lidJid = jidNormalizedUser(c.lid);
            lidToPhone[lidJid] = c.id.split('@')[0];
            const name = c.name || c.notify || c.verifiedName || '';
            if (name) lidToPushName[lidJid] = name;
          } catch { /* skip malformed LID */ }
        }
      }

      const batch = [];
      const seenLids = new Set();

      for (const c of (contacts || [])) {
        if (!c.notify && !c.verifiedName && !c.name) continue;
        const wa_contact_id = jidNormalizedUser(c.id);
        let phone_number = '';
        if (c.id.endsWith('@s.whatsapp.net')) {
          phone_number = c.id.split('@')[0];
        } else if (c.id.endsWith('@lid')) {
          seenLids.add(wa_contact_id);
          phone_number = lidToPhone[wa_contact_id] || '';
        }
        batch.push({
          wa_contact_id,
          push_name: c.name || c.notify || c.verifiedName || '',
          phone_number,
        });
      }

      // Synthetic entries for LID contacts that only appeared as a phone contact's lid field.
      // These are LID JIDs we found a phone for, but that didn't show up separately in the list.
      for (const [lidJid, phone] of Object.entries(lidToPhone)) {
        if (!seenLids.has(lidJid) && lidToPushName[lidJid]) {
          batch.push({ wa_contact_id: lidJid, push_name: lidToPushName[lidJid], phone_number: phone });
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
      const lidCount = (contacts || []).filter(c => c.id?.endsWith('@lid')).length;
      const mappableCount = (contacts || []).filter(c => c.id?.endsWith('@s.whatsapp.net') && c.lid).length;
      this.logger.info(
        { sessionId, total: (contacts || []).length, lidContacts: lidCount, lidMappable: mappableCount },
        'Contacts.set received',
      );
      await _sendNamedContacts(contacts);
    });

    sock.ev.on('contacts.upsert', async (contacts) => {
      await _sendNamedContacts(contacts);
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
    if (msg.key.remoteJid === 'status@broadcast') return null;
    if (msg.messageStubType) return null;
    if (msg.message?.protocolMessage) return null;
    if (msg.message?.senderKeyDistributionMessage) return null;

    const rawJid = msg.key.remoteJid;

    // When WhatsApp privacy mode is active, remoteJid arrives as a LID (e.g. 249868530499648@lid).
    // Baileys provides the real phone JID in msg.key.senderPn for 1-on-1 chats.
    const isLidJid = rawJid?.endsWith('@lid');
    const senderPn = msg.key.senderPn;
    const resolvedJid = (isLidJid && senderPn) ? senderPn : rawJid;

    const chatId = jidNormalizedUser(resolvedJid);
    const isGroup = chatId?.endsWith('@g.us');
    const rawSenderJid = msg.key.participant || resolvedJid;
    const senderJid = jidNormalizedUser(rawSenderJid);
    const senderNumber = senderJid?.split('@')[0] || '';
    const fromMe = msg.key.fromMe;
    const messageTimestamp = msg.messageTimestamp
      ? new Date(Number(msg.messageTimestamp) * 1000).toISOString()
      : new Date().toISOString();

    const { messageType, messageText, hasMedia, mediaMimeType } = this._parseMessage(msg);

    const session = this.sessions.get(sessionId);
    const groupName = isGroup ? await this._getGroupName(session.sock, chatId) : '';

    let safeRaw = null;
    try { safeRaw = JSON.parse(JSON.stringify(msg)); } catch { safeRaw = null; }

    const direction = (fromMe === true) ? 'outbound' : 'inbound';

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

  async _forwardMessage(sessionId, msg) {
    try {
      const built = await this._buildPayload(sessionId, msg);
      if (!built) return;

      const { payload, logEntry } = built;
      try {
        await this.djangoClient.sendMessageIngest(payload);
      } catch (fwdErr) {
        logEntry.forward_status = 'error';
        logEntry.forward_error  = fwdErr.message;
        throw fwdErr;
      } finally {
        this.messageLogger.write(sessionId, logEntry);
      }
    } catch (err) {
      this.logger.error({ sessionId, msgId: msg.key?.id, err: err.message }, 'Failed to forward message');
    }
  }

  async _forwardHistoryBatch(sessionId, msgs) {
    const CHUNK_SIZE = 100;

    // Build all payloads (filters protocol messages; fetches group names via cache)
    const built = [];
    for (const msg of msgs) {
      try {
        const result = await this._buildPayload(sessionId, msg, { isHistory: true });
        if (result) built.push(result);
      } catch (err) {
        this.logger.warn({ sessionId, msgId: msg.key?.id, err: err.message }, 'Failed to build history payload — skipping');
      }
    }

    if (!built.length) return;

    this.logger.info({ sessionId, total: built.length, chunks: Math.ceil(built.length / CHUNK_SIZE) }, 'Sending history batch to Django');

    for (let i = 0; i < built.length; i += CHUNK_SIZE) {
      const chunk = built.slice(i, i + CHUNK_SIZE);
      const payloads = chunk.map(b => b.payload);

      let forwardStatus = 'success';
      let forwardError = null;

      try {
        await this.djangoClient.sendMessageIngestBatch(payloads);
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
    };
  }
}

module.exports = { SessionManager, SESSION_STATUS };
