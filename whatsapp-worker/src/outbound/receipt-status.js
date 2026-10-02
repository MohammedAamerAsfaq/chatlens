'use strict';

function normalizeReceiptStatus(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  if (numeric >= 4) return 'read';
  if (numeric >= 3) return 'delivered';
  if (numeric >= 2) return 'sent';
  return null;
}

module.exports = { normalizeReceiptStatus };
