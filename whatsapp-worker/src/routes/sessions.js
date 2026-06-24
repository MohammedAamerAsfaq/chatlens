'use strict';

const { Router } = require('express');

module.exports = function sessionsRouter(sessionManager) {
  const router = Router();

  // POST /sessions
  // Body: { session_id: string }
  // Creates (or re-attaches) a WhatsApp session and begins QR generation.
  router.post('/', async (req, res) => {
    const { session_id } = req.body;
    if (!session_id) {
      return res.status(400).json({ error: 'session_id is required' });
    }

    try {
      const snapshot = await sessionManager.createSession(session_id);
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

  // POST /sessions/:id/disconnect
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

  return router;
};
