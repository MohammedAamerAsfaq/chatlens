<script setup>
import { ref, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { tradingApi } from '@/api'

// Share one inquiry with colleagues. People who already get it through their
// "share all" setting are shown as such and cannot be unticked here.
const props = defineProps({
  inquiry: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const recipients = ref([])
const selected = ref({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')

function errorText(exc, fallback) {
  return exc.response?.data?.detail || exc.message || fallback
}

watch(() => props.inquiry?.id, async (id) => {
  recipients.value = []
  selected.value = {}
  error.value = ''
  if (!id) return
  loading.value = true
  try {
    const { data } = await tradingApi.getInquiryShares(id)
    recipients.value = data.recipients
    selected.value = Object.fromEntries(data.recipients.map(r => [r.id, r.shared]))
  } catch (exc) {
    error.value = errorText(exc, 'Unable to load who this inquiry is shared with.')
  } finally {
    loading.value = false
  }
}, { immediate: true })

async function save() {
  saving.value = true
  error.value = ''
  try {
    const ids = recipients.value.filter(r => selected.value[r.id]).map(r => r.id)
    await tradingApi.setInquiryShares(props.inquiry.id, ids)
    emit('saved')
    emit('close')
  } catch (exc) {
    error.value = errorText(exc, 'Unable to share this inquiry.')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UiModal
    :open="Boolean(inquiry)"
    title="Share inquiry"
    :subtitle="inquiry ? (inquiry.contact_name || inquiry.contact_phone || inquiry.summary) : ''"
    size="small"
    @close="emit('close')"
  >
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <p v-if="loading" class="share-note">Loading…</p>
    <p v-else-if="!recipients.length" class="share-note">There is nobody else in your company who can view the Trading board.</p>
    <div v-else class="share-list">
      <UiCheckbox
        v-for="person in recipients"
        :key="person.id"
        v-model="selected[person.id]"
        :label="person.name"
        :description="person.shared_by_rule ? 'Already receives it through Share all' : ''"
        :disabled="person.shared_by_rule"
      />
    </div>
    <p class="share-note">They work it with their own status. Their actions never change yours; you will see who handled it on the card.</p>
    <template #footer>
      <UiButton @click="emit('close')">Cancel</UiButton>
      <UiButton variant="primary" :disabled="loading || saving || !recipients.length" @click="save">{{ saving ? 'Saving…' : 'Save' }}</UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.share-list{display:grid;gap:8px;margin-bottom:12px}.share-note{margin:0 0 10px;color:var(--ui-text-muted);font-size:.8rem;line-height:1.4}
</style>
