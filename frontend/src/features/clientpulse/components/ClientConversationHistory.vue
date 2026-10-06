<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { clientPulseApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({ profileId: { type: Number, required: true } })
const messages = ref([]), accounts = ref([]), selectedAccount = ref('')
const loading = ref(true), error = ref(''), page = ref(1), count = ref(0)
const pageSize = 25
const pages = computed(() => Math.max(1, Math.ceil(count.value / pageSize)))
const orderedMessages = computed(() => [...messages.value].reverse())
const accountOptions = computed(() => [
  { value: '', label: 'All linked accounts' },
  ...accounts.value.map(account => ({
    value: account.id,
    label: `${account.name}${account.phone_number ? ` / ${account.phone_number}` : ''}`,
  })),
])

function mediaSource(url) {
  return url ? url.replace(/^\/media\//, '/worker-media/') : ''
}
function displayText(message) {
  if (message.message_text) return message.message_text
  return message.has_media ? `[${message.message_type || 'media'}]` : '[Empty message]'
}
function formatDate(value) {
  return new Date(value).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}
function formatTime(value) {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
function isNewDay(index) {
  if (index === 0) return true
  return new Date(orderedMessages.value[index - 1].message_time).toDateString()
    !== new Date(orderedMessages.value[index].message_time).toDateString()
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const params = { page: page.value, page_size: pageSize }
    if (selectedAccount.value) params.account_id = selectedAccount.value
    const { data } = await clientPulseApi.conversations(props.profileId, params)
    messages.value = data.results; count.value = data.count; accounts.value = data.accounts
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to load conversation history.'
  } finally { loading.value = false }
}
function changePage(value) { page.value = value; load() }
watch(selectedAccount, () => { page.value = 1; load() })
onMounted(load)
</script>

<template>
  <UiCard title="Conversation history" :subtitle="`${count} direct messages across linked communication accounts`" class="client-conversations">
    <template #actions><div class="client-conversations__tools"><UiSelect v-model="selectedAccount" :options="accountOptions" /><UiButton size="small" variant="outline" :disabled="loading" @click="load">Refresh</UiButton></div></template>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiEmptyState v-if="loading" title="Loading conversation history" description="Retrieving direct messages from linked communication accounts." busy />
    <UiEmptyState v-else-if="!accounts.length" title="No linked communication account" description="Link a WhatsApp contact before conversation history can be displayed." />
    <UiEmptyState v-else-if="!messages.length" title="No direct messages found" description="This client has no stored direct-chat history for the selected account." />
    <div v-else class="client-conversations__history">
      <template v-for="(message, index) in orderedMessages" :key="message.id">
        <div v-if="isNewDay(index)" class="client-conversations__date"><span>{{ formatDate(message.message_time) }}</span></div>
        <article class="client-conversations__row" :class="`is-${message.direction}`">
          <div class="client-conversations__bubble">
            <div class="client-conversations__meta"><UiBadge :tone="message.account_status === 'connected' ? 'success' : 'neutral'">{{ message.account_name }}</UiBadge><span>{{ formatTime(message.message_time) }}</span></div>
            <img v-if="message.message_type === 'image' && mediaSource(message.media_url)" :src="mediaSource(message.media_url)" :alt="message.media_file_name || 'Conversation image'" loading="lazy" />
            <a v-else-if="message.has_media && mediaSource(message.media_url)" :href="mediaSource(message.media_url)" target="_blank" rel="noopener">{{ message.media_file_name || `Open ${message.message_type}` }}</a>
            <p>{{ displayText(message) }}</p>
          </div>
        </article>
      </template>
    </div>
    <UiPagination v-if="pages > 1" :page="page" :pages="pages" @change="changePage" />
  </UiCard>
</template>

<style scoped>
.client-conversations__tools{display:flex;align-items:center;gap:8px}.client-conversations__tools :deep(.choices){min-width:230px}.client-conversations__history{max-height:560px;overflow:auto;padding:16px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:color-mix(in srgb,var(--ui-surface-muted) 72%,var(--ui-surface))}.client-conversations__date{display:flex;justify-content:center;margin:10px 0}.client-conversations__date span{padding:4px 9px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-pill);background:var(--ui-surface);color:var(--ui-text-muted);font-size:.68rem}.client-conversations__row{display:flex;margin:7px 0;justify-content:flex-start}.client-conversations__row.is-outbound{justify-content:flex-end}.client-conversations__bubble{width:min(76%,680px);padding:10px 12px;border:1px solid var(--ui-border);border-radius:12px 12px 12px 3px;background:var(--ui-surface);box-shadow:var(--ui-shadow-card)}.is-outbound .client-conversations__bubble{border-color:color-mix(in srgb,var(--ui-primary) 20%,var(--ui-border));border-radius:12px 12px 3px 12px;background:var(--ui-primary-soft)}.client-conversations__meta{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px;color:var(--ui-text-subtle);font-size:.68rem}.client-conversations__bubble p{margin:0;color:var(--ui-text);font-size:.8rem;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}.client-conversations__bubble img{display:block;max-width:min(100%,360px);max-height:300px;margin-bottom:8px;border-radius:var(--ui-radius-sm);object-fit:cover}.client-conversations__bubble a{display:block;margin-bottom:7px;color:var(--ui-primary);font-size:.76rem;font-weight:700}@media(max-width:700px){.client-conversations__tools{align-items:stretch;flex-direction:column}.client-conversations__tools :deep(.choices){min-width:0}.client-conversations__bubble{width:92%}}
</style>
