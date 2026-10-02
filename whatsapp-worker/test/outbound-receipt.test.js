'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizeReceiptStatus } = require('../src/outbound/receipt-status');

test('normalizes Baileys acknowledgement levels monotonically', () => {
  assert.equal(normalizeReceiptStatus(1), null);
  assert.equal(normalizeReceiptStatus(2), 'sent');
  assert.equal(normalizeReceiptStatus(3), 'delivered');
  assert.equal(normalizeReceiptStatus(4), 'read');
  assert.equal(normalizeReceiptStatus(5), 'read');
});
