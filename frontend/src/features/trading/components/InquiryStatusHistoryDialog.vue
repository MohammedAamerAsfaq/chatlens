<script setup>
import { ref, watch } from 'vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { tradingApi } from '@/api'

// Every change to an inquiry's status: who made it, from what, to what, and when.
const props = defineProps({
  inquiry: { type: Object, default: null },
})
const emit = defineEmits(['close'])

const events = ref([])
const loading = ref(false)
const error = ref('')

watch(() => props.inquiry?.id, async (id) => {
  events.value = []
  error.value = ''
  if (!id) return
  loading.value = true
  try {
    const { data } = await tradingApi.getInquiryStatusHistory(id)
    events.value = data.results
  } catch (exc) {
    error.value = exc.response?.data?.detail || exc.message || 'Unable to load the status history.'
  } finally {
    loading.value = false
  }
}, { immediate: true })

function formatTime(iso) {
  return new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}
</script>

<template>
  <UiModal
    :open="Boolean(inquiry)"
    title="Status history"
    :subtitle="inquiry ? (inquiry.contact_name || inquiry.contact_phone || inquiry.summary) : ''"
    size="small"
    @close="emit('close')"
  >
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <p v-if="loading" class="history-note">Loading…</p>
    <p v-else-if="!events.length && !error" class="history-note">No status changes recorded yet.</p>
    <ol v-else class="history">
      <li v-for="event in events" :key="event.id">
        <div class="history-line">
          <strong>{{ event.user_name }}</strong>
          <span v-if="event.old_status_label">{{ event.old_status_label }} → </span><span class="to">{{ event.new_status_label }}</span>
          <span v-if="event.source !== 'update'" class="source">{{ event.source_label }}</span>
        </div>
        <div class="history-meta">{{ formatTime(event.created_at) }}<template v-if="event.remarks"> · {{ event.remarks }}</template></div>
      </li>
    </ol>
  </UiModal>
</template>

<style scoped>
.history{display:grid;gap:10px;margin:0;padding:0;list-style:none}.history li{padding-bottom:10px;border-bottom:1px solid var(--ui-border)}.history li:last-child{border-bottom:0}.history-line{display:flex;flex-wrap:wrap;align-items:center;gap:6px;color:var(--ui-text);font-size:.85rem}.to{font-weight:700}.source{padding:1px 7px;border-radius:var(--ui-radius-pill);background:var(--ui-surface-muted);color:var(--ui-text-muted);font-size:.7rem}.history-meta{margin-top:2px;color:var(--ui-text-muted);font-size:.76rem}.history-note{margin:0;color:var(--ui-text-muted);font-size:.84rem}
</style>
