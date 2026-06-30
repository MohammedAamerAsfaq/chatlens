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
      // LID → phone JID mapping built from contacts.set/upsert.
      // Used to normalise outbound LID chat_ids (which have no senderPn).
      lidToPhone: {},
      // username (bare handle, no @domain) → full phone JID.
      // Populated from contacts.set when c.username is present.
      // Used to resolve username-keyed chat JIDs once WhatsApp usernames roll out.
      usernameToPhone: {},
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
      session.lastActivityAt = Date.now();

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
        this.logger.debug({ sessionId, type, count: messages.length }, 'messages.upsert — unhandled type, skipping');
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

        const wa_contact_id = jidNormalizedUser(c.id);
        if (!wa_contact_id) continue;

        const phone_number = c.id?.endsWith('@s.whatsapp.net') ? c.id.split('@')[0] : '';
        const lid_jid  = phoneToLid[wa_contact_id]      || null;
        const username = phoneToUsername[wa_contact_id]  || null;

        batch.push({ wa_contact_id, push_name: name, phone_number, lid_jid, username });
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
    if (msg.message?.protocolMessage) return _skip('protocolMessage');

    // Drop senderKeyDistributionMessage ONLY when it is the sole content of the envelope.
    // WhatsApp often bundles the key distribution with a real user message (text/media) in
    // a single envelope — dropping the whole envelope in that case silently loses the message.
    // Pure key envelopes (no other content besides optional messageContextInfo) are safe to drop.
    if (msg.message?.senderKeyDistributionMessage) {
      const METADATA_KEYS = new Set(['senderKeyDistributionMessage', 'messageContextInfo']);
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

    // Resolve alias JIDs → canonical phone JID so every contact has exactly one identity.
    //
    // LID priority (individual chat where remoteJid IS a LID):
    //   1. senderPn on inbound — Baileys' most reliable real-time resolution; cache it.
    //   2. session.lidToPhone  — built from contacts.set/upsert before any messages arrive.
    //   Drop 'unresolvable_lid' if neither resolves.
    //
    // Username priority (individual chat where remoteJid has a non-digit local part):
    //   1. session.usernameToPhone — built from contacts.set when c.username is present.
    //   Drop 'unresolvable_username' if not in cache.
    //   TODO(baileys-username ~Jul 2026): Baileys may also expose msg.key.senderPn here
    //   (same field as LID resolution). Add that as priority-1 once confirmed and cache it.
    //
    // Group JIDs and normal phone JIDs are passed through unchanged.
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
        return _skip('unresolvable_lid');
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
    const messageTimestamp = msg.messageTimestamp
      ? new Date(Number(msg.messageTimestamp) * 1000).toISOString()
      : new Date().toISOString();

    const { messageType, messageText, hasMedia, mediaMimeType } = this._parseMessage(msg);

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
    } catch (fwdErr) {
      logEntry.forward_status = 'error';
      logEntry.forward_error  = fwdErr.message;
      this.logger.error({ sessionId, msgId: msg.key?.id, err: fwdErr.message }, 'Failed to forward message to Django');
      this._reportDropped(sessionId, msg, 'forward_failed');
    } finally {
      this.messageLogger.write(sessionId, logEntry);
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
