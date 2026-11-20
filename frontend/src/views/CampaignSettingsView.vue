<script setup>
import { computed, onMounted, ref } from 'vue'
import { tradingApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import { CampaignCurrencyForm, blankCurrencySettings } from '@/features/campaigns'

// Company-wide campaign settings. Currency: how campaign messages show prices; a campaign
// can override it from its own edit form.
const auth = useAuthStore()
const canEdit = computed(() => auth.hasPermission('settings.company.manage'))
const settings = ref(null)
const errors = ref({})
const error = ref('')
const notice = ref('')
const saving = ref(false)

async function load() {
  try {
    settings.value = blankCurrencySettings((await tradingApi.getCampaignCurrencySettings()).data)
  } catch (exc) {
    error.value = exc?.response?.data?.detail || 'Unable to load the campaign currency settings.'
  }
}
async function save() {
  saving.value = true; error.value = ''; notice.value = ''; errors.value = {}
  try {
    settings.value = blankCurrencySettings((await tradingApi.setCampaignCurrencySettings(settings.value)).data)
    notice.value = 'Currency settings saved. Campaigns without their own settings use them from now on.'
  } catch (exc) {
    const data = exc?.response?.data
    if (data && typeof data === 'object' && !data.detail) {
      errors.value = data
      error.value = Object.values(data).flat().join(' ')
    } else {
      error.value = data?.detail || 'Unable to save the currency settings.'
    }
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <UiPage>
    <UiPageHeader eyebrow="Campaigns" title="Campaign settings" description="Company defaults for campaign messages. A campaign can override them from its edit form." />
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-else-if="notice" tone="success">{{ notice }}</UiNotice>
    <UiCard title="Currency" subtitle="How {price} appears in campaign product lines: a primary currency, optionally followed by converted prices.">
      <UiEmptyState v-if="!settings" title="Loading settings..." busy />
      <template v-else>
        <CampaignCurrencyForm :settings="settings" :errors="errors" :disabled="!canEdit || saving" />
        <div v-if="canEdit" class="campaign-settings__actions">
          <UiButton variant="primary" :disabled="saving" @click="save">{{ saving ? 'Saving...' : 'Save currency settings' }}</UiButton>
        </div>
        <p v-else class="campaign-settings__hint">Only company administrators can change these settings.</p>
      </template>
    </UiCard>
  </UiPage>
</template>

<style scoped>
.campaign-settings__actions{display:flex;justify-content:flex-end;margin-top:14px}
.campaign-settings__hint{margin:12px 0 0;color:var(--ui-text-muted);font-size:.78rem}
</style>
