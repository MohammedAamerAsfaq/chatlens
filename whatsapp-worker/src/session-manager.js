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

class SessionManager {
  constructor({ sessionStorePath, djangoClient, logger }) {
    this.sessionStorePath = sessionStorePath;
    this.djangoClient = djangoClient;
    this.logger = logger;
    // Map<sessionId, { sock, status, qrDataUrl, phoneNumber, displayName }>
    this.sessions = new Map();

    if (!fs.existsSync(sessionStorePath)) {
      fs.mkdirSync(sessionStorePath, { recursive: true });
    }
  }

  // ─── Public API ────────────────────────────────────────────────────────────

  async createSession(sessionId) {
    if (this.sessions.has(sessionId)) {
      return this._snapshot(sessionId);
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
      if (type !== 'notify') return;

      for (const msg of messages) {
        if (msg.key.fromMe === undefined) continue;
        await this._forwardMessage(sessionId, msg);
      }
    });
  }

  async _forwardMessage(sessionId, msg) {
    try {
      const isGroup = msg.key.remoteJid?.endsWith('@g.us');
      const chatId = msg.key.remoteJid;
      const senderJid = msg.key.participant || msg.key.remoteJid;
      const senderNumber = senderJid?.split('@')[0] || '';
      const fromMe = msg.key.fromMe;
      const messageTimestamp = msg.messageTimestamp
        ? new Date(Number(msg.messageTimestamp) * 1000).toISOString()
        : new Date().toISOString();

      const { messageType, messageText, hasMedia, mediaMimeType } = this._parseMessage(msg);

      const payload = {
        worker_session_id: sessionId,
        provider_message_id: msg.key.id,
        chat_id: chatId,
        chat_type: isGroup ? 'group' : 'individual',
        sender_number: senderNumber,
        direction: fromMe ? 'outbound' : 'inbound',
        message_type: messageType,
        message_text: messageText,
        message_time: messageTimestamp,
        has_media: hasMedia,
        media_mime_type: mediaMimeType,
        raw_payload: msg,
      };

      await this.djangoClient.sendMessageIngest(payload);
    } catch (err) {
      this.logger.error({ sessionId, msgId: msg.key.id, err: err.message }, 'Failed to forward message');
    }
  }

  _parseMessage(msg) {
    const m = msg.message || {};

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
