<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { clientPulseApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'

const props = defineProps({ profileId: { type: Number, required: true } })
const messages = ref([]), accounts = ref([]), selectedAccount = ref(''), conversationType = ref('dm')
const loading = ref(true), loadingMore = ref(false), error = ref('')
const page = ref(1), count = ref(0), hasMore = ref(false)
const expanded = ref(true), historyEl = ref(null)
const pageSize = 25
const conversationTabs = [
  { value: 'dm', label: 'DM Messages' },
  { value: 'group', label: 'Group Messages' },
  { value: 'announcement', label: 'Announcements' },
]
const activeTab = computed(() => conversationTabs.find(tab => tab.value === conversationType.value))
const sectionCopy = computed(() => ({
  dm: {
    loading: 'Retrieving direct messages from linked communication accounts.',
    emptyTitle: 'No direct messages found',
    emptyDescription: 'This client has no stored direct-chat history for the selected account.',
  },
  group: {
    loading: 'Retrieving messages this client sent in connected groups.',
    emptyTitle: 'No group messages found',
    emptyDescription: 'This client has no stored messages in regular groups for the selected account.',
  },
  announcement: {
    loading: 'Retrieving messages this client sent in connected announcement groups.',
    emptyTitle: 'No announcement messages found',
    emptyDescription: 'This client has no stored messages in announcement groups for the selected account.',
  },
})[conversationType.value])
const orderedMessages = computed(() => [...messages.value].reverse())
const accountOptions = computed(() => [
  { value: '', label: 'All linked accounts' },
  ...accounts.value.map(account => ({
    value: account.id,
    label: `${account.name}${account.phone_number ? ` / ${account.phone_number}` : ''}`,
  })),
])

function mediaSource(url) { return url ? url.replace(/^\/media\//, '/worker-media/') : '' }
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
function scrollToLatest() {
  if (historyEl.value) historyEl.value.scrollTop = historyEl.value.scrollHeight
}
async function load({ reset = false } = {}) {
  if (loadingMore.value || (loading.value && !reset)) return
  const element = historyEl.value
  const previousHeight = element?.scrollHeight || 0
  const previousTop = element?.scrollTop || 0
  if (reset) {
    loading.value = true; page.value = 1; messages.value = []
  } else loadingMore.value = true
  error.value = ''
  try {
    const params = { page: page.value, page_size: pageSize, conversation_type: conversationType.value }
    if (selectedAccount.value) params.account_id = selectedAccount.value
    const { data } = await clientPulseApi.conversations(props.profileId, params)
    const known = new Set(messages.value.map(message => message.id))
    messages.value = reset
      ? data.results
      : [...messages.value, ...data.results.filter(message => !known.has(message.id))]
    count.value = data.count; accounts.value = data.accounts; hasMore.value = Boolean(data.next)
    await nextTick()
    if (reset) scrollToLatest()
    else if (element) element.scrollTop = element.scrollHeight - previousHeight + previousTop
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to load conversation history.'
  } finally { loading.value = false; loadingMore.value = false }
}
async function loadEarlier() {
  if (!hasMore.value || loading.value || loadingMore.value) return
  page.value += 1
  await load()
  if (error.value) page.value -= 1
}
function onHistoryScroll(event) {
  if (event.currentTarget.scrollTop <= 80) loadEarlier()
}
function refresh() { load({ reset: true }) }
function toggleExpanded() {
  expanded.value = !expanded.value
  if (expanded.value) nextTick(scrollToLatest)
}
watch([selectedAccount, conversationType], refresh)
onMounted(refresh)
</script>

<template>
  <UiCard
    title="Conversation history"
    :subtitle="`${count} ${activeTab.label.toLowerCase()} across linked communication accounts`"
    class="client-conversations"
    :class="{ 'is-collapsed': !expanded }"
  >
    <template #actions>
      <div class="client-conversations__tools">
        <UiSelect v-if="expanded" v-model="selectedAccount" :options="accountOptions" aria-label="Communication account" />
        <UiButton v-if="expanded" variant="outline" :disabled="loading || loadingMore" @click="refresh">Refresh</UiButton>
        <UiButton variant="outline" :aria-expanded="expanded" @click="toggleExpanded">
          {{ expanded ? 'Collapse' : 'Expand' }} <span aria-hidden="true">{{ expanded ? '-' : '+' }}</span>
        </UiButton>
      </div>
    </template>
    <template v-if="expanded">
      <UiTabs v-model="conversationType" :tabs="conversationTabs" />
      <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
      <UiEmptyState v-if="loading" title="Loading conversation history" :description="sectionCopy.loading" busy />
      <UiEmptyState v-else-if="!accounts.length" title="No linked communication account" description="Link a WhatsApp contact before conversation history can be displayed." />
      <UiEmptyState v-else-if="!messages.length" :title="sectionCopy.emptyTitle" :description="sectionCopy.emptyDescription" />
      <div v-else ref="historyEl" class="client-conversations__history" data-testid="conversation-history" @scroll.passive="onHistoryScroll">
        <div class="client-conversations__loader">
          <span v-if="loadingMore">Loading earlier messages...</span>
          <span v-else-if="hasMore">Scroll up to load earlier messages</span>
          <span v-else>Beginning of conversation history</span>
        </div>
        <template v-for="(message, index) in orderedMessages" :key="message.id">
          <div v-if="isNewDay(index)" class="client-conversations__date"><span>{{ formatDate(message.message_time) }}</span></div>
          <article class="client-conversations__row" :class="`is-${message.direction}`">
            <div class="client-conversations__bubble">
              <div class="client-conversations__meta"><div><UiBadge :tone="message.account_status === 'connected' ? 'success' : 'neutral'">{{ message.sender_name || (message.direction === 'inbound' ? message.contact_name : message.account_name) }}</UiBadge><strong v-if="message.conversation_type !== 'dm'">{{ message.chat_name }}</strong></div><span>{{ formatTime(message.message_time) }}</span></div>
              <img v-if="message.message_type === 'image' && mediaSource(message.media_url)" :src="mediaSource(message.media_url)" :alt="message.media_file_name || 'Conversation image'" loading="lazy" />
              <a v-else-if="message.has_media && mediaSource(message.media_url)" :href="mediaSource(message.media_url)" target="_blank" rel="noopener">{{ message.media_file_name || `Open ${message.message_type}` }}</a>
              <p>{{ displayText(message) }}</p>
            </div>
          </article>
        </template>
      </div>
    </template>
  </UiCard>
</template>

<style scoped>
.client-conversations :deep(.ui-card__header){align-items:center}.client-conversations.is-collapsed :deep(.ui-card__body){display:none}.client-conversations :deep(.ui-tabs){margin-bottom:14px}.client-conversations__tools{display:flex;align-items:center;justify-content:flex-end;gap:8px}.client-conversations__tools :deep(.choices){width:280px;min-width:220px;margin:0}.client-conversations__tools :deep(.ui-button){min-height:42px;white-space:nowrap}.client-conversations__history{min-height:240px;max-height:min(600px,65vh);overflow:auto;padding:16px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:color-mix(in srgb,var(--ui-surface-muted) 72%,var(--ui-surface));scroll-behavior:auto}.client-conversations__loader{display:flex;justify-content:center;min-height:28px;color:var(--ui-text-subtle);font-size:.68rem}.client-conversations__date{display:flex;justify-content:center;margin:10px 0}.client-conversations__date span{padding:4px 9px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-pill);background:var(--ui-surface);color:var(--ui-text-muted);font-size:.68rem}.client-conversations__row{display:flex;margin:7px 0;justify-content:flex-start}.client-conversations__row.is-outbound{justify-content:flex-end}.client-conversations__bubble{width:min(76%,680px);padding:10px 12px;border:1px solid var(--ui-border);border-radius:12px 12px 12px 3px;background:var(--ui-surface);box-shadow:var(--ui-shadow-card)}.is-outbound .client-conversations__bubble{border-color:color-mix(in srgb,var(--ui-primary) 20%,var(--ui-border));border-radius:12px 12px 3px 12px;background:var(--ui-primary-soft)}.client-conversations__meta{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px;color:var(--ui-text-subtle);font-size:.68rem}.client-conversations__meta>div{display:flex;min-width:0;align-items:center;gap:7px}.client-conversations__meta strong{overflow:hidden;color:var(--ui-text-muted);font-size:.68rem;text-overflow:ellipsis;white-space:nowrap}.client-conversations__bubble p{margin:0;color:var(--ui-text);font-size:.8rem;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}.client-conversations__bubble img{display:block;max-width:min(100%,360px);max-height:300px;margin-bottom:8px;border-radius:var(--ui-radius-sm);object-fit:cover}.client-conversations__bubble a{display:block;margin-bottom:7px;color:var(--ui-primary);font-size:.76rem;font-weight:700}@media(max-width:760px){.client-conversations :deep(.ui-card__header){align-items:stretch;flex-direction:column}.client-conversations__tools{align-items:stretch;display:grid;grid-template-columns:1fr 1fr}.client-conversations__tools :deep(.choices){grid-column:1/-1;width:100%;min-width:0}.client-conversations__bubble{width:92%}}
</style>
