'use strict';

require('dotenv').config();

const fs = require('fs');
const path = require('path');
const pino = require('pino');
const QRCode = require('qrcode');
const {
  makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  Browsers,
} = require('@whiskeysockets/baileys');

function parseVersion(value) {
  if (!value) return null;
  const parts = String(value).split(',').map(part => Number.parseInt(part.trim(), 10));
  if (parts.length !== 3 || parts.some(part => !Number.isInteger(part))) {
    throw new Error('WHATSAPP_WEB_VERSION must contain three comma-separated integers.');
  }
  return parts;
}

async function resolveVersion() {
  const configured = parseVersion(process.env.WHATSAPP_WEB_VERSION);
  if (configured) {
    return { version: configured, source: 'env', isLatest: null };
  }

  const fetched = await fetchLatestBaileysVersion();
  return {
    version: fetched.version,
    source: 'fetchLatestBaileysVersion',
    isLatest: fetched.isLatest,
    fetchError: fetched.error?.code || fetched.error?.message || null,
  };
}

async function main() {
  const authDir = path.resolve(process.env.DIAGNOSTIC_SESSION_PATH || './diagnostic-qr-session');
  const clean = process.env.DIAGNOSTIC_CLEAN !== '0';
  if (clean && fs.existsSync(authDir)) {
    fs.rmSync(authDir, { recursive: true, force: true });
  }
  fs.mkdirSync(authDir, { recursive: true });

  const logger = pino({ level: process.env.LOG_LEVEL || 'debug' });
  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const versionInfo = await resolveVersion();

  logger.info({
    authDir,
    version: versionInfo.version,
    source: versionInfo.source,
    isLatest: versionInfo.isLatest,
    fetchError: versionInfo.fetchError || null,
    browser: Browsers.ubuntu('Chrome'),
  }, 'Starting standalone Baileys QR diagnostic');

  const sock = makeWASocket({
    version: versionInfo.version,
    auth: state,
    browser: Browsers.ubuntu('Chrome'),
    printQRInTerminal: false,
    logger,
  });

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      const qrDataUrl = await QRCode.toDataURL(qr);
      logger.info({ qrLength: qr.length, qrDataUrlLength: qrDataUrl.length }, 'QR generated successfully');
      console.log('QR_GENERATED');
      console.log(qrDataUrl.slice(0, 120) + '...');
      process.exitCode = 0;
      setTimeout(() => process.exit(0), 500);
      return;
    }

    if (connection === 'open') {
      logger.info({ user: sock.user }, 'Connected without needing QR');
      process.exitCode = 0;
      setTimeout(() => process.exit(0), 500);
      return;
    }

    if (connection === 'close') {
      const err = lastDisconnect?.error;
      logger.error({
        message: err?.message || '',
        name: err?.name || '',
        stack: err?.stack || '',
        output: err?.output || null,
        data: err?.data || null,
      }, 'Standalone Baileys QR diagnostic closed before QR');
      process.exitCode = 2;
      setTimeout(() => process.exit(2), 500);
    }
  });

  setTimeout(() => {
    logger.error('Timed out waiting for QR or close event');
    process.exit(3);
  }, Number.parseInt(process.env.DIAGNOSTIC_TIMEOUT_MS || '45000', 10));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
