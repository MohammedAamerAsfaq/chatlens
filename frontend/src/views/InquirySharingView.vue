<script setup>
import { computed, onMounted, ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import { tradingApi } from '@/api'

const settings = ref(null)
const selected = ref({})
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref('')

const changed = computed(() => (settings.value?.recipients || []).some(r => Boolean(selected.value[r.id]) !== r.shared))

function errorText(exc, fallback) {
  return exc.response?.data?.detail || exc.message || fallback
}

function apply(data) {
  settings.value = data
  selected.value = Object.fromEntries(data.recipients.map(r => [r.id, r.shared]))
}

function since(iso) {
  return iso ? `Sharing since ${new Date(iso).toLocaleString()}` : ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.getInquirySharing()
    apply(data)
  } catch (exc) {
    error.value = errorText(exc, 'Unable to load inquiry sharing.')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  saved.value = ''
  try {
    const ids = settings.value.recipients.filter(r => selected.value[r.id]).map(r => r.id)
    const { data } = await tradingApi.setInquirySharing(ids)
    apply(data)
    saved.value = 'Inquiry sharing saved.'
  } catch (exc) {
    error.value = errorText(exc, 'Unable to save inquiry sharing.')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <UiPage class="inquiry-sharing-page">
    <UiPageHeader
      eyebrow="Trading"
      title="Inquiry Sharing"
      description="Share every new inquiry on the WhatsApp accounts you own with colleagues. You can also share single inquiries from the Trading board."
    />

    <UiCard title="Share all my new inquiries with">
      <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
      <UiNotice v-if="saved" tone="success">{{ saved }}</UiNotice>
      <p v-if="loading" class="note">Loading…</p>
      <template v-else-if="settings">
        <UiNotice v-if="!settings.owns_accounts" tone="warning">
          You do not own a WhatsApp account, so there are no inquiries of yours to share.
        </UiNotice>
        <p v-else-if="!settings.recipients.length" class="note">There is nobody else in your company who can view the Trading board.</p>
        <div v-else class="recipients">
          <UiCheckbox
            v-for="person in settings.recipients"
            :key="person.id"
            v-model="selected[person.id]"
            :label="person.name"
            :description="since(person.since)"
          />
        </div>
        <ul class="note">
          <li>Only inquiries that arrive after you switch sharing on are shared. Switching it off hides them again; switching it back on starts from that moment.</li>
          <li>Each person works a shared inquiry with their own status. Their actions never change yours, and yours never change theirs.</li>
          <li>On your cards you see who handled an inquiry and what they did.</li>
        </ul>
        <UiButton v-if="settings.owns_accounts && settings.recipients.length" variant="primary" :disabled="saving || !changed" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </UiButton>
      </template>
    </UiCard>
  </UiPage>
</template>

<style scoped>
.inquiry-sharing-page{display:grid;gap:16px}.recipients{display:grid;gap:10px;margin-bottom:14px}.note{margin:0 0 14px;padding-left:18px;color:var(--ui-text-muted);font-size:.84rem;line-height:1.5}p.note{padding-left:0}
</style>
