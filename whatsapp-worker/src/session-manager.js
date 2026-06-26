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
  constructor({ sessionStorePath, djangoClient, logger }) {
    this.sessionStorePath = sessionStorePath;
    this.mediaStorePath = path.join(path.dirname(sessionStorePath), 'media');
    this.djangoClient = djangoClient;
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
      // Check if credentials file exists — if not, session was logged out and cleared
      const credsFile = path.join(this.sessionStorePath, sessionId, 'creds.json');
      if (!fs.existsSync(credsFile)) {
        this.logger.info({ sessionId }, 'Skipping session — no credentials on disk (was logged out)');
        continue;
      }
      this.logger.info({ sessionId }, 'Restoring session');
      await this.createSession(sessionId);
    }
  }

  async createSession(sessionId) {
    const existing = this.sessions.get(sessionId);
    if (existing?.sock) {
      // Active socket exists — already connected or connecting
      return this._snapshot(sessionId);
    }

    // If previously logged out, wipe credentials so Baileys starts fresh and generates a QR
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
    });
    await this._connect(sessionId);
    return this._snapshot(sessionId);
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

    const sock = makeWASocket({
      version,
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })),
      },
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }),
      shouldIgnoreJid: jid => isJidBroadcast(jid),
      syncFullHistory: true,
      getMessage: async () => ({ conversation: '' }),
    });

    const session = this.sessions.get(sessionId);
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
        this.logger.info({ sessionId, phone: session.phoneNumber }, 'Session connected');
        await this.djangoClient.sendSessionStatus(sessionId, {
          status: SESSION_STATUS.CONNECTED,
          phone_number: session.phoneNumber,
          display_name: session.displayName,
        });
      }

      if (connection === 'close') {
        const code = lastDisconnect?.error?.output?.statusCode;
        const loggedOut = code === DisconnectReason.loggedOut;

        session.status = loggedOut ? SESSION_STATUS.LOGGED_OUT : SESSION_STATUS.DISCONNECTED;
        session.sock = null;
        this.logger.info({ sessionId, code, loggedOut }, 'Session closed');

        await this.djangoClient.sendSessionStatus(sessionId, {
          status: session.status,
        });

        if (!loggedOut) {
          this.logger.info({ sessionId }, 'Reconnecting in 5s');
          setTimeout(() => this._connect(sessionId), 5000);
        }
      }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      // 'notify' = real-time new message
      // 'append' = backfill of messages received while offline
      if (type !== 'notify' && type !== 'append') return;

      for (const msg of messages) {
        if (!msg.key?.remoteJid) continue;   // skip protocol stubs with no JID
        if (!msg.message) continue;           // skip key-only stubs with no content
        await this._forwardMessage(sessionId, msg);
      }
    });

    sock.ev.on('messaging-history.set', async ({ messages, isLatest }) => {
      this.logger.info({ sessionId, count: messages.length, isLatest }, 'History sync received');
      for (const msg of messages) {
        if (!msg.key?.remoteJid) continue;
        if (!msg.message) continue;
        await this._forwardMessage(sessionId, msg);
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

  async _forwardMessage(sessionId, msg) {
    try {
      // Normalize JID to strip device suffix (e.g. 971501234567:5@s.whatsapp.net → 971501234567@s.whatsapp.net)
      // Without this, inbound and outbound for the same contact can land in two separate chat records.
      const rawJid = msg.key.remoteJid;
      const chatId = jidNormalizedUser(rawJid);
      const isGroup = chatId?.endsWith('@g.us');
      const rawSenderJid = msg.key.participant || rawJid;
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

      // fromMe may be undefined for some Baileys message types — default to inbound
      const direction = (fromMe === true) ? 'outbound' : 'inbound';

      // Download media to disk and expose via the worker's /media route
      let mediaUrl = null;
      if (hasMedia) {
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
      };

      await this.djangoClient.sendMessageIngest(payload);
    } catch (err) {
      this.logger.error({ sessionId, msgId: msg.key.id, err: err.message }, 'Failed to forward message');
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
