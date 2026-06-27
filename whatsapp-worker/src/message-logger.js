'use strict';

const fs   = require('fs');
const path = require('path');

class MessageLogger {
  constructor(logsDir) {
    this.logsDir = logsDir;
    fs.mkdirSync(logsDir, { recursive: true });
  }

  _filePath(sessionId) {
    return path.join(this.logsDir, `messages-${sessionId}.ndjson`);
  }

  // Append one JSON entry per line — never throws (log failures must not crash the pipeline)
  write(sessionId, entry) {
    try {
      fs.appendFileSync(this._filePath(sessionId), JSON.stringify(entry) + '\n', 'utf8');
    } catch { /* swallow */ }
  }

  // Read all entries for a session, newest first, with pagination and optional message_id filter
  read(sessionId, { page = 1, pageSize = 25, messageId = null } = {}) {
    const filePath = this._filePath(sessionId);
    if (!fs.existsSync(filePath)) {
      return { count: 0, results: [], page, page_size: pageSize };
    }

    const raw = fs.readFileSync(filePath, 'utf8');
    const entries = [];
    for (const line of raw.split('\n')) {
      if (!line.trim()) continue;
      try { entries.push(JSON.parse(line)); } catch { /* skip malformed lines */ }
    }

    // Newest first
    entries.reverse();

    const filtered = messageId
      ? entries.filter(e => e.provider_message_id === messageId)
      : entries;

    const count   = filtered.length;
    const start   = (page - 1) * pageSize;
    const results = filtered.slice(start, start + pageSize);

    return { count, results, page, page_size: pageSize };
  }

  // Delete the log file for a session
  clear(sessionId) {
    try {
      const fp = this._filePath(sessionId);
      if (fs.existsSync(fp)) fs.unlinkSync(fp);
    } catch { /* swallow */ }
  }

  // Size of the log file in bytes, 0 if absent
  size(sessionId) {
    try {
      const fp = this._filePath(sessionId);
      return fs.existsSync(fp) ? fs.statSync(fp).size : 0;
    } catch { return 0; }
  }
}

module.exports = { MessageLogger };
