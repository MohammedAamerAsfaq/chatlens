<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { accountsApi, clientPulseApi, outboundAssetsApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiFileUpload from '@/components/ui/UiFileUpload.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({ client: { type: Object, required: true } })
const emit = defineEmits(['queued'])
const targetId = ref(props.client.whatsapp_contacts?.[0]?.id || '')
const text = ref(''), image = ref(null), preview = ref(''), assetId = ref(null)
const busy = ref(false), error = ref(''), feedback = ref(''), preflight = ref(null)
let attemptKey = ''

const contacts = computed(() => props.client.whatsapp_contacts || [])
const contactOptions = computed(() => contacts.value.map(item => ({ value: item.id, label: `${item.account_name} / ${item.display_name || item.phone_number}` })))
const target = computed(() => contacts.value.find(item => item.id === Number(targetId.value)))
const limit = computed(() => image.value ? 1024 : 10000)
const count = computed(() => [...text.value].length)
const targetReady = computed(() => Boolean(target.value?.sending_enabled && target.value?.direct_sending_enabled && (!image.value || target.value?.image_sending_enabled)))
const ready = computed(() => Boolean(target.value && (text.value.trim() || image.value) && count.value <= limit.value && targetReady.value && !busy.value && !props.client.do_not_contact && props.client.status === 'active'))

function newKey() {
  return typeof globalThis.crypto?.randomUUID === 'function' ? globalThis.crypto.randomUUID() : `cp-${Date.now()}-${Math.random().toString(36).slice(2)}`
}
function resetAttempt() { attemptKey = '' }
function clearImage() {
  if (preview.value) URL.revokeObjectURL(preview.value)
  image.value = null; preview.value = ''; assetId.value = null; resetAttempt()
}
function selectImage(file) {
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
    error.value = 'Select a JPEG, PNG, or WebP image no larger than 10 MB.'; return
  }
  clearImage(); image.value = file; preview.value = URL.createObjectURL(file)
}
function apiMessage(exc, fallback) {
  const data = exc.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
async function queue(confirmNewChat = false) {
  if (!ready.value) return
  busy.value = true; error.value = ''; feedback.value = ''; preflight.value = null
  try {
    const check = await accountsApi.preflightMessage(target.value.account_id, target.value.wa_contact_id)
    preflight.value = check.data
    if (!check.data.allowed) throw new Error(`Preflight blocked: ${check.data.reason}`)
    if (image.value && !assetId.value) assetId.value = (await outboundAssetsApi.upload(image.value)).data.id
    if (!attemptKey) attemptKey = newKey()
    const response = await clientPulseApi.sendFollowUp(props.client.id, {
      whatsapp_contact_id: target.value.id, text: text.value.trim(), asset_id: assetId.value,
      idempotency_key: attemptKey, confirm_new_chat: confirmNewChat,
    })
    const result = response.data
    if (result.status === 'preflight_blocked') {
      error.value = `Sending blocked: ${result.status_reason}`; attemptKey = ''
    } else {
      const advisory = result.consent.mode === 'observational' && result.consent.status !== 'granted' ? ` Consent observed as ${result.consent.status}.` : ''
      feedback.value = `Queued as outbound #${result.id}.${advisory}`
      text.value = ''; clearImage(); attemptKey = ''; emit('queued', result)
    }
  } catch (exc) {
    if (exc.response?.status === 409 && exc.response?.data?.code === 'likely_new_chat_confirmation_required') {
      if (confirm('This may start a new WhatsApp chat and use new-chat capacity. Continue?')) {
        busy.value = false; await queue(true); return
      }
    } else {
      error.value = exc instanceof Error && !exc.response ? exc.message : apiMessage(exc, 'Unable to queue follow-up.')
    }
  } finally { busy.value = false }
}
watch([targetId, text], resetAttempt)
onBeforeUnmount(() => { if (preview.value) URL.revokeObjectURL(preview.value) })
</script>

<template>
  <UiCard title="WhatsApp follow-up" subtitle="Live preflight and all account sending restrictions are checked before this message enters the durable queue.">
    <template #actions><UiBadge tone="info" dot>Outbound queue</UiBadge></template>
    <UiNotice v-if="client.do_not_contact" tone="danger">Blocked by this client's do-not-contact setting.</UiNotice>
    <UiNotice v-else-if="client.status !== 'active'" tone="danger">Only active clients can receive a manual follow-up.</UiNotice>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="feedback" tone="success">{{ feedback }}</UiNotice>
    <div v-if="contacts.length" class="follow-up__grid">
      <UiFormField label="Linked destination"><UiSelect v-model="targetId" :options="contactOptions" /></UiFormField>
      <div v-if="target" class="follow-up__state"><div><strong>{{ target.account_name }}</strong><small>{{ target.session_status }} / {{ target.is_existing_chat ? 'Existing chat' : 'Marked as new chat' }}</small></div><UiBadge :tone="targetReady ? 'success' : 'danger'">{{ targetReady ? 'Ready' : 'Sending disabled' }}</UiBadge></div>
      <UiNotice v-if="target && !targetReady" class="follow-up__wide" tone="danger">Enable direct sending and, when attaching an image, image sending for the selected account.</UiNotice>
      <UiFormField class="follow-up__wide" label="Message or image caption"><UiInput v-model="text" multiline :rows="6" placeholder="Write a personal follow-up..." /></UiFormField>
      <div class="follow-up__wide follow-up__counter" :class="{ invalid: count > limit }"><strong>{{ count.toLocaleString() }} / {{ limit.toLocaleString() }}</strong><span>{{ image ? 'image caption' : 'text message' }}</span></div>
      <div class="follow-up__wide"><UiFileUpload accept="image/jpeg,image/png,image/webp" :file-name="image?.name || ''" :label="image ? 'Replace image' : 'Attach image'" @select="selectImage" @clear="clearImage" /><small class="follow-up__hint">JPEG, PNG, or WebP / maximum 10 MB</small></div>
      <div v-if="image" class="follow-up__wide follow-up__preview"><img :src="preview" :alt="image.name" /><div><strong>{{ image.name }}</strong><small>{{ Math.ceil(image.size / 1024).toLocaleString() }} KB</small></div></div>
      <div class="follow-up__wide follow-up__actions"><UiButton variant="primary" :disabled="!ready" @click="queue(false)">{{ busy ? 'Checking...' : 'Check and queue' }}</UiButton></div>
    </div>
    <UiEmptyState v-else title="No WhatsApp contact linked" description="Link a WhatsApp contact to this client before sending a follow-up." />
  </UiCard>
</template>

<style scoped>
.follow-up__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: end; }
.follow-up__wide { grid-column: 1 / -1; }
.follow-up__state { display: flex; min-height: var(--ui-control-height); align-items: center; justify-content: space-between; gap: 12px; padding: 7px 10px; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-sm); background: var(--ui-surface-muted); }
.follow-up__state strong,.follow-up__state small,.follow-up__preview small { display: block; }
.follow-up__state strong,.follow-up__preview strong { color: var(--ui-text-strong); font-size: .78rem; }
.follow-up__state small,.follow-up__preview small,.follow-up__hint { margin-top: 3px; color: var(--ui-text-subtle); font-size: .7rem; }
.follow-up__counter { display: flex; justify-content: flex-end; gap: 7px; color: var(--ui-text-muted); font-size: .72rem; }
.follow-up__counter.invalid { color: var(--ui-danger); }
.follow-up__preview { display: flex; align-items: center; gap: 12px; padding: 10px; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-sm); background: var(--ui-surface-muted); }
.follow-up__preview img { width: 70px; height: 70px; border-radius: var(--ui-radius-sm); object-fit: cover; }
.follow-up__actions { display: flex; justify-content: flex-end; }
@media (max-width: 760px) { .follow-up__grid { grid-template-columns: 1fr; } }
</style>
