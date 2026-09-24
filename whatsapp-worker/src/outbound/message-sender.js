'use strict';

const crypto = require('crypto');

const { DESTINATION, classifyDestination, normalizeGroupMetadata } = require('./destination-classifier');
const { fetchGroupMetadata } = require('./group-metadata');

class OutboundMessageSender {
  constructor({ assetLoader = null } = {}) {
    this.states = new Map();
    this.assetLoader = assetLoader;
  }

  _state(sessionId) {
    if (!this.states.has(sessionId)) {
      this.states.set(sessionId, { inFlight: 0, lastAccountStart: 0, recipients: new Map(), sent: new Map() });
    }
    return this.states.get(sessionId);
  }

  async _content(request) {
    if (request.content_type === 'text') {
      return { text: String(request.content?.text || '') };
    }
    if (request.content_type !== 'image' || !this.assetLoader) {
      throw new Error('unsupported_outbound_content');
    }
    const expected = request.content || {};
    const asset = await this.assetLoader(expected.asset_id);
    const digest = crypto.createHash('sha256').update(asset.buffer).digest('hex');
    if (Number(expected.size_bytes) !== asset.buffer.length || expected.sha256 !== digest) {
      throw new Error('outbound_asset_integrity_failed');
    }
    if (expected.mime_type !== asset.mimeType) {
      throw new Error('outbound_asset_mime_mismatch');
    }
    return { image: asset.buffer, caption: String(expected.caption || '') };
  }

  async send(sessionId, session, request) {
    const state = this._state(sessionId);
    const jid = String(request.destination_jid || '').trim().toLowerCase();
    const providerId = String(request.provider_message_id || '');
    if (state.sent.has(providerId)) return { ...state.sent.get(providerId), duplicate: true };
    if (!session?.sock || session.status !== 'connected') {
      return { accepted: false, retryable: true, dispatch_started: false, code: 'session_disconnected' };
    }

    let type = classifyDestination(jid);
    if (type === DESTINATION.DIRECT) {
      if (jid.endsWith('@lid')) {
        return { accepted: false, retryable: false, dispatch_started: false, code: 'recipient_identity_unresolved' };
      }
      const matches = await session.sock.onWhatsApp(jid);
      if (!matches?.some(item => item.exists)) {
        return { accepted: false, retryable: false, dispatch_started: false, code: 'recipient_not_registered' };
      }
    } else if ([DESTINATION.GROUP].includes(type)) {
      const metadata = await fetchGroupMetadata(session.sock, jid);
      const normalized = normalizeGroupMetadata(
        metadata,
        session.accountIdentity || session.sock.user,
      );
      type = classifyDestination(jid, metadata);
      if (!normalized.can_send) {
        return { accepted: false, retryable: false, dispatch_started: false, code: normalized.send_block_reason };
      }
    } else {
      const code = type === DESTINATION.COMMUNITY ? 'community_send_blocked'
        : type === DESTINATION.CHANNEL ? 'channel_send_blocked' : 'destination_unsupported';
      return { accepted: false, retryable: false, dispatch_started: false, code };
    }

    const settings = request.settings || {};
    const now = Date.now();
    const accountInterval = Math.max(1000, Number(settings.account_interval_ms || 5000));
    const recipientInterval = Math.max(1000, Number(settings.recipient_interval_ms || 5000));
    const maxConcurrent = settings.allow_concurrent_sends
      ? Math.max(1, Number(settings.max_concurrent_sends || 1)) : 1;
    const recipient = state.recipients.get(jid) || { lastStart: 0, inFlight: 0 };
    const eligibleAt = Math.max(state.lastAccountStart + accountInterval, recipient.lastStart + recipientInterval);
    if (eligibleAt > now) {
      return { accepted: false, retryable: true, dispatch_started: false, code: 'node_interval_wait', retry_after_ms: eligibleAt - now };
    }
    if (state.inFlight >= maxConcurrent || recipient.inFlight > 0) {
      return { accepted: false, retryable: true, dispatch_started: false, code: 'node_concurrency_wait' };
    }

    let content;
    try {
      content = await this._content(request);
    } catch (error) {
      return {
        accepted: false,
        retryable: true,
        dispatch_started: false,
        code: 'asset_fetch_failed',
        error: error?.message || String(error),
      };
    }

    state.inFlight += 1;
    state.lastAccountStart = now;
    recipient.inFlight += 1;
    recipient.lastStart = now;
    state.recipients.set(jid, recipient);
    try {
      const result = await session.sock.sendMessage(
        jid,
        content,
        { messageId: providerId },
      );
      const response = {
        accepted: true,
        dispatch_started: true,
        provider_message_id: result?.key?.id || providerId,
        destination_type: type,
      };
      state.sent.set(providerId, response);
      if (state.sent.size > 5000) state.sent.delete(state.sent.keys().next().value);
      return response;
    } catch (error) {
      return {
        accepted: false,
        dispatch_started: true,
        outcome_unknown: true,
        code: 'dispatch_outcome_unknown',
        error: error?.message || String(error),
      };
    } finally {
      state.inFlight = Math.max(0, state.inFlight - 1);
      recipient.inFlight = Math.max(0, recipient.inFlight - 1);
    }
  }
}

module.exports = { OutboundMessageSender };
