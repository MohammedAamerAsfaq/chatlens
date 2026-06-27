'use strict';

const path = require('path');
const fs = require('fs');
const { Router } = require('express');

function dirSizeSync(dir) {
  let fileCount = 0;
  let totalBytes = 0;
  if (!fs.existsSync(dir)) return { fileCount, totalBytes };
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) { walk(full); }
      else { fileCount++; totalBytes += fs.statSync(full).size; }
    }
  };
  walk(dir);
  return { fileCount, totalBytes };
}

module.exports = function sessionsRouter(sessionManager, mediaStorePath) {
  const router = Router();

  // POST /sessions
  // Body: { session_id: string }
  // Creates (or re-attaches) a WhatsApp session and begins QR generation.
  router.post('/', async (req, res) => {
    const { session_id, sync_history, history_days, idle_disconnect_minutes } = req.body;
    if (!session_id) {
      return res.status(400).json({ error: 'session_id is required' });
    }

    try {
      const snapshot = await sessionManager.createSession(session_id, {
        sync_history,
        history_days,
        idle_disconnect_minutes,
      });
      return res.status(201).json(snapshot);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  // GET /sessions
  // Returns list of all active sessions.
  router.get('/', (req, res) => {
    return res.json(sessionManager.listSessions());
  });

  // GET /sessions/:id/status
  router.get('/:id/status', (req, res) => {
    const snapshot = sessionManager.getStatus(req.params.id);
    if (!snapshot) return res.status(404).json({ error: 'Session not found' });
    return res.json(snapshot);
  });

  // GET /sessions/:id/qr
  // Returns the current QR code as a base64 data URL (image/png).
  // Poll this endpoint until status becomes 'connected'.
  router.get('/:id/qr', (req, res) => {
    const snapshot = sessionManager.getStatus(req.params.id);
    if (!snapshot) return res.status(404).json({ error: 'Session not found' });

    const qrDataUrl = sessionManager.getQR(req.params.id);
    if (!qrDataUrl) {
      return res.status(202).json({
        message: 'QR not ready yet',
        status: snapshot.status,
      });
    }

    return res.json({ qr: qrDataUrl, status: snapshot.status });
  });

  // POST /sessions/:id/disconnect  (full logout — requires QR on next connect)
  router.post('/:id/disconnect', async (req, res) => {
    const snapshot = sessionManager.getStatus(req.params.id);
    if (!snapshot) return res.status(404).json({ error: 'Session not found' });

    try {
      await sessionManager.disconnect(req.params.id);
      return res.json({ success: true });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  // POST /sessions/:id/soft-disconnect  (stays offline but keeps credentials — no QR needed to reconnect)
  router.post('/:id/soft-disconnect', async (req, res) => {
    try {
      await sessionManager.softDisconnect(req.params.id);
      return res.json({ success: true });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  // GET /sessions/:id/storage  — media file count + total bytes on disk for this session
  router.get('/:id/storage', (req, res) => {
    const mediaDir = path.join(path.resolve(mediaStorePath), String(req.params.id));
    const { fileCount, totalBytes } = dirSizeSync(mediaDir);
    return res.json({ file_count: fileCount, total_bytes: totalBytes });
  });

  // GET /sessions/:id/groups/:groupJid — live group metadata (participants, description, etc.)
  router.get('/:id/groups/:groupJid', async (req, res) => {
    try {
      const meta = await sessionManager.getGroupMetadata(req.params.id, req.params.groupJid);
      if (!meta) return res.status(404).json({ error: 'Session not connected or group not found' });
      return res.json(meta);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  return router;
};
