import { reactive } from 'vue'
import { accountsApi, outboundAssetsApi } from '@/api'

const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_IMAGE_BYTES = 10 * 1024 * 1024
const MAX_CAPTION_LENGTH = 1024
const PREFLIGHT_REASONS = {
  direct_sending_disabled: 'Direct-message sending is disabled for this account.',
  live_preflight_unavailable: 'WhatsApp worker preflight is unavailable.',
  master_sending_disabled: 'Outbound sending is disabled for this account.',
  recipient_not_registered: 'This number is not registered on WhatsApp.',
  session_disconnected: 'WhatsApp session is disconnected.',
}
const OUTBOUND_REASONS = {
  image_sending_disabled: 'Image sending is disabled for this account.',
  new_chat_cap_reached: "WhatsApp reports that this account's new-chat limit has been reached.",
  new_chat_cap_unknown: 'The current new-chat capacity is unknown and this account is configured to block it.',
  reachout_locked: 'WhatsApp has temporarily restricted new outgoing conversations for this account.',
}

function requestKey(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function useDirectCampaignSender({ kind, markClick, updateRecipient }) {
  const images = reactive({})
  const assetIds = reactive({})
  const feedback = reactive({})
  const busy = reactive({})

  const rowKey = (campaignId, recipientId) => `${campaignId}:${recipientId}`

  function selectImage(campaignId, event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return ''
    if (!IMAGE_TYPES.includes(file.type) || file.size > MAX_IMAGE_BYTES) {
      return 'Select a JPEG, PNG, or WebP image no larger than 10 MB.'
    }
    images[campaignId] = file
    delete assetIds[campaignId]
    return ''
  }

  function removeImage(campaignId) {
    delete images[campaignId]
    delete assetIds[campaignId]
  }

  async function queue(campaign, recipient, text, confirmNewChat, idempotencyKey) {
    const payload = {
      destination_jid: recipient.destination_jid,
      text,
      asset_id: assetIds[campaign.id] || null,
      idempotency_key: idempotencyKey,
      confirm_new_chat: confirmNewChat,
    }
    try {
      return await accountsApi.sendMessage(recipient.account_id, payload)
    } catch (exc) {
      if (exc.response?.data?.code !== 'likely_new_chat_confirmation_required') throw exc
      if (!window.confirm('This may start a new chat. Send the message anyway?')) throw new Error('Send cancelled.')
      return accountsApi.sendMessage(recipient.account_id, { ...payload, confirm_new_chat: true })
    }
  }

  async function send(campaign, recipient, text) {
    const key = rowKey(campaign.id, recipient.id)
    busy[key] = true
    feedback[key] = { state: 'checking', message: 'Checking recipient...' }
    try {
      if (!recipient.account_id || !recipient.destination_jid) {
        throw new Error('This contact has no sendable WhatsApp destination.')
      }
      if (images[campaign.id] && text.length > MAX_CAPTION_LENGTH) {
        throw new Error(`Image captions cannot exceed ${MAX_CAPTION_LENGTH} characters.`)
      }

      const clickResponse = await markClick(campaign.id, recipient.id)
      updateRecipient(campaign.id, clickResponse.data)

      const preflight = await accountsApi.preflightMessage(recipient.account_id, recipient.destination_jid)
      if (!preflight.data.allowed) {
        throw new Error(PREFLIGHT_REASONS[preflight.data.reason] || preflight.data.reason || 'Sending is blocked for this contact.')
      }
      if (images[campaign.id] && !assetIds[campaign.id]) {
        feedback[key] = { state: 'uploading', message: 'Uploading image...' }
        const { data: asset } = await outboundAssetsApi.upload(images[campaign.id])
        assetIds[campaign.id] = asset.id
      }

      feedback[key] = { state: 'queueing', message: 'Queueing message...' }
      const { data } = await queue(
        campaign,
        recipient,
        text,
        false,
        requestKey(`${kind}-${campaign.id}-${recipient.id}`),
      )
      if (['blocked', 'preflight_blocked', 'failed'].includes(data.status)) {
        throw new Error(
          OUTBOUND_REASONS[data.status_reason]
          || data.status_reason
          || data.last_error
          || 'Outbound message was blocked.',
        )
      }
      feedback[key] = { state: 'queued', message: images[campaign.id] ? 'Image and caption queued.' : 'Message queued.' }
    } catch (exc) {
      feedback[key] = {
        state: 'failed',
        message: exc.response?.data?.detail || exc.message || 'Unable to queue message.',
      }
    } finally {
      delete busy[key]
    }
  }

  return { assetIds, busy, feedback, images, removeImage, rowKey, selectImage, send }
}
