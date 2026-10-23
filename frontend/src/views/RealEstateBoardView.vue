<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import OpportunityDetailModal from '@/features/realEstate/components/OpportunityDetailModal.vue'
import OpportunityLane from '@/features/realEstate/components/OpportunityLane.vue'
import { opportunityLanes, opportunityStatuses, statusFilters } from '@/features/realEstate/boardOptions'
import { cardFields, defaultCardFieldIds } from '@/features/realEstate/cardFields'
import { apiError } from '@/features/realEstate/apiErrors'
import { useAuthStore } from '@/stores/auth'

const COLUMNS_STORAGE_KEY = 'chatlens:real-estate-board:columns'
const PAGE_SIZE_STORAGE_KEY = 'chatlens:real-estate-board:page-size'
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

function loadStoredColumns() {
  try {
    const stored = Number(localStorage.getItem(COLUMNS_STORAGE_KEY))
    return [1, 2, 3].includes(stored) ? stored : 1
  } catch {
    return 1
  }
}

function loadStoredPageSize() {
  try {
    const stored = Number(localStorage.getItem(PAGE_SIZE_STORAGE_KEY))
    return PAGE_SIZE_OPTIONS.includes(stored) ? stored : 20
  } catch {
    return 20
  }
}

const auth = useAuthStore()
const search = ref('')
const status = ref('')
const activeLaneKey = ref(opportunityLanes[0].key)
const columns = ref(loadStoredColumns())
watch(columns, value => {
  try {
    localStorage.setItem(COLUMNS_STORAGE_KEY, value)
  } catch {
    // Private-browsing/storage-blocked viewers just lose the preference across reloads.
  }
})
const pageSize = ref(loadStoredPageSize())
const pageSizeOptions = PAGE_SIZE_OPTIONS.map(value => ({ value, label: String(value) }))
watch(pageSize, value => {
  try {
    localStorage.setItem(PAGE_SIZE_STORAGE_KEY, value)
  } catch {
    // Private-browsing/storage-blocked viewers just lose the preference across reloads.
  }
  for (const lane of opportunityLanes) laneStates[lane.key].page = 1
  loadAll()
})
const selected = ref(null)
const properties = ref([])
const saving = ref(false)
const globalError = ref('')
const cardFieldIds = ref([...defaultCardFieldIds])
const cardActionConfig = ref({ statuses: [], max_inline: 2 })
const cardConfigOpen = ref(false)
const cardConfigSaving = ref(false)
const cardConfigError = ref('')
const laneStates = reactive(Object.fromEntries(opportunityLanes.map(lane => [lane.key, {
  rows: [], total: 0, page: 1, loading: false, error: '', requestId: 0,
}])))
const canUpdate = computed(() => auth.hasPermission('real_estate.opportunities.update'))
const totalOpportunities = computed(() => opportunityLanes.reduce((sum, lane) => sum + laneStates[lane.key].total, 0))
const laneTabs = computed(() => opportunityLanes.map(lane => ({
  value: lane.key,
  label: lane.label,
  count: laneStates[lane.key].total,
})))
const activeLane = computed(() => opportunityLanes.find(lane => lane.key === activeLaneKey.value) || opportunityLanes[0])
let searchTimer

async function loadLane(lane, { resetPage = true } = {}) {
  const state = laneStates[lane.key]
  const requestId = state.requestId + 1
  state.requestId = requestId
  state.loading = true
  state.error = ''
  if (resetPage) state.page = 1
  try {
    const { data } = await realEstateApi.opportunities({
      activity_type: lane.key,
      classification_status: 'classified',
      status: status.value || undefined,
      search: search.value.trim() || undefined,
      page: state.page,
      page_size: pageSize.value,
    })
    if (requestId !== state.requestId) return
    state.rows = data.results || data
    state.total = data.count ?? state.rows.length
  } catch (exc) {
    if (requestId === state.requestId) {
      state.error = apiError(exc, `Unable to load ${lane.label.toLowerCase()}.`)
    }
  } finally {
    if (requestId === state.requestId) state.loading = false
  }
}

async function loadAll() {
  globalError.value = ''
  await Promise.all(opportunityLanes.map(lane => loadLane(lane)))
}

async function loadProperties() {
  try {
    const { data } = await realEstateApi.properties({ page_size: 100, ordering: 'title' })
    properties.value = data.results || data
  } catch (exc) {
    globalError.value = apiError(exc, 'Unable to load properties for matching.')
  }
}

function goToPage(lane, page) {
  laneStates[lane.key].page = page
  loadLane(lane, { resetPage: false })
}

async function setOpportunityStatus(opportunity, nextStatus) {
  saving.value = true
  globalError.value = ''
  try {
    const { data } = await realEstateApi.updateOpportunity(opportunity.id, { status: nextStatus })
    if (selected.value?.id === data.id) selected.value = data
    const state = laneStates[data.activity_type]
    const index = state?.rows.findIndex(row => row.id === data.id) ?? -1
    if (index >= 0) state.rows[index] = data
  } catch (exc) {
    globalError.value = apiError(exc, 'Unable to update the opportunity status.')
  } finally {
    saving.value = false
  }
}

function saveStatus(nextStatus) {
  if (!selected.value) return
  return setOpportunityStatus(selected.value, nextStatus)
}

async function loadCardConfig() {
  try {
    const [fieldsRes, actionsRes] = await Promise.all([
      realEstateApi.getCardFieldConfig(), realEstateApi.getCardActionConfig(),
    ])
    cardFieldIds.value = fieldsRes.data.fields?.length ? fieldsRes.data.fields : [...defaultCardFieldIds]
    cardActionConfig.value = actionsRes.data
  } catch {
    // Non-real-estate/non-member viewers can't reach these — card just keeps its defaults.
  }
}

async function saveCardFieldConfig(fields) {
  cardConfigSaving.value = true
  cardConfigError.value = ''
  try {
    const { data } = await realEstateApi.setCardFieldConfig(fields)
    cardFieldIds.value = data.fields
  } catch (exc) {
    cardConfigError.value = apiError(exc, 'Unable to save card field settings.')
  } finally {
    cardConfigSaving.value = false
  }
}

async function saveCardActionConfig(statuses, maxInline) {
  cardConfigSaving.value = true
  cardConfigError.value = ''
  try {
    const { data } = await realEstateApi.setCardActionConfig(statuses, maxInline)
    cardActionConfig.value = data
  } catch (exc) {
    cardConfigError.value = apiError(exc, 'Unable to save card action settings.')
  } finally {
    cardConfigSaving.value = false
  }
}

function toggleCardField(id) {
  const next = cardFieldIds.value.includes(id)
    ? cardFieldIds.value.filter(value => value !== id)
    : [...cardFieldIds.value, id]
  saveCardFieldConfig(next)
}

function toggleCardAction(id) {
  const current = cardActionConfig.value.statuses || []
  const next = current.includes(id) ? current.filter(value => value !== id) : [...current, id]
  saveCardActionConfig(next, cardActionConfig.value.max_inline ?? 2)
}

function setCardActionMaxInline(value) {
  const maxInline = Math.max(0, Number(value) || 0)
  saveCardActionConfig(cardActionConfig.value.statuses || [], maxInline)
}

function replaceSelectedItem(updated) {
  if (!selected.value) return
  selected.value.items = selected.value.items.map(item => item.id === updated.id ? updated : item)
  const state = laneStates[selected.value.activity_type]
  const row = state?.rows.find(item => item.id === selected.value.id)
  if (row) row.items = selected.value.items
}

async function itemAction(action, item, propertyId = null) {
  saving.value = true; globalError.value = ''
  try {
    let response
    if (action === 'link') response = await realEstateApi.linkOpportunityItem(item.id, propertyId)
    else if (action === 'unlink') response = await realEstateApi.unlinkOpportunityItem(item.id)
    else response = await realEstateApi.createPropertyFromOpportunityItem(item.id)
    replaceSelectedItem(response.data.item || response.data)
    if (action === 'create') await loadProperties()
  } catch (exc) {
    globalError.value = apiError(exc, 'Unable to update the property link.')
  } finally { saving.value = false }
}

watch(status, loadAll)
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadAll, 350)
})
onMounted(() => Promise.all([loadAll(), loadProperties(), loadCardConfig()]))
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>

<template>
  <UiPage width="full">
    <UiNotice v-if="globalError" tone="danger">{{ globalError }}</UiNotice>
    <UiCard class="board-toolbar">
      <div class="board-toolbar__controls">
        <UiInput v-model="search" placeholder="Search party, phone, location, summary, or message...">
          <template #prefix><i class="fa-solid fa-magnifying-glass"></i></template>
        </UiInput>
        <UiSelect v-model="status" :options="statusFilters" />
      </div>
      <div class="board-actions">
        <div class="board-field board-field--columns">
          <span class="board-field__label">Columns</span>
          <div class="board-columns" role="group" aria-label="Cards per row">
            <UiButton
              v-for="n in 3" :key="n" size="small" :variant="columns === n ? 'soft' : 'default'"
              @click="columns = n"
            >{{ n }}</UiButton>
          </div>
        </div>
        <div class="board-field">
          <span class="board-field__label">Per page</span>
          <UiSelect v-model="pageSize" class="board-page-size__select" :options="pageSizeOptions" />
        </div>
        <div class="board-total"><strong>{{ totalOpportunities }}</strong><span>visible opportunities</span></div>
        <UiButton v-if="auth.isCompanyAdmin" size="small" @click="cardConfigOpen = !cardConfigOpen">
          Card Display{{ cardConfigOpen ? ' ▴' : ' ▾' }}
        </UiButton>
        <UiButton variant="primary" @click="loadAll">Refresh board</UiButton>
      </div>
    </UiCard>

    <UiCard v-if="cardConfigOpen && auth.isCompanyAdmin" class="card-config">
      <UiNotice v-if="cardConfigError" tone="danger">{{ cardConfigError }}</UiNotice>
      <div class="card-config__section">
        <h4>Card fields</h4>
        <p>Choose which attributes show on each card. The first header field becomes the card title.</p>
        <div class="card-config__checks">
          <label v-for="field in cardFields" :key="field.id">
            <input
              type="checkbox" :checked="cardFieldIds.includes(field.id)" :disabled="cardConfigSaving"
              @change="toggleCardField(field.id)"
            />
            {{ field.label }} <small>({{ field.section }})</small>
          </label>
        </div>
      </div>
      <div class="card-config__section">
        <h4>Quick status actions</h4>
        <p>Choose which statuses get a one-click button in the card footer, and how many show before collapsing into a "More" menu.</p>
        <div class="card-config__checks">
          <label v-for="s in opportunityStatuses" :key="s.value">
            <input
              type="checkbox" :checked="(cardActionConfig.statuses || []).includes(s.value)" :disabled="cardConfigSaving"
              @change="toggleCardAction(s.value)"
            />
            {{ s.label }}
          </label>
        </div>
        <label class="card-config__max-inline">
          Buttons shown before overflow
          <input
            type="number" min="0" :value="cardActionConfig.max_inline ?? 2" :disabled="cardConfigSaving"
            @change="setCardActionMaxInline($event.target.value)"
          />
        </label>
      </div>
    </UiCard>

    <div class="opportunity-board">
      <div class="opportunity-board__tabs">
        <UiTabs v-model="activeLaneKey" :tabs="laneTabs" />
      </div>
      <OpportunityLane
        :key="activeLane.key"
        :columns="columns"
        :lane="activeLane"
        :state="laneStates[activeLane.key]"
        :page-size="pageSize"
        :field-ids="cardFieldIds"
        :action-config="cardActionConfig"
        expanded
        @change-page="goToPage"
        @open="selected = $event"
        @set-status="setOpportunityStatus"
      />
    </div>

    <OpportunityDetailModal
      :open="Boolean(selected)"
      :opportunity="selected"
      :can-update="canUpdate"
      :properties="properties"
      :busy="saving"
      @close="selected = null"
      @save="saveStatus"
      @link-item="(item, propertyId) => itemAction('link', item, propertyId)"
      @unlink-item="item => itemAction('unlink', item)"
      @create-property="item => itemAction('create', item)"
    />
  </UiPage>
</template>

<style scoped>
.board-actions{display:flex;flex-shrink:0;align-items:flex-end;justify-content:flex-end;gap:16px}.board-field{display:flex;flex-direction:column;gap:4px}.board-field__label{color:var(--ui-text-subtle);font-size:.62rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase}.board-columns{display:flex;gap:4px;padding:3px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface)}.board-columns :deep(.ui-button){min-width:28px}.board-page-size__select{width:76px}.board-total{display:flex;align-items:center;gap:8px;padding:7px 11px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface)}.board-total strong{color:var(--ui-primary);font-size:1rem}.board-total span{color:var(--ui-text-muted);font-size:.68rem}.board-toolbar{margin-bottom:14px}.board-toolbar :deep(.ui-card__body){display:flex;align-items:center;justify-content:space-between;gap:18px;padding:12px}.board-toolbar__controls{display:grid;grid-template-columns:minmax(260px,520px) 190px;gap:10px;flex:1}.opportunity-board{min-width:0}.opportunity-board__tabs{margin-bottom:12px;padding:0 8px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.opportunity-board__tabs :deep(.ui-tabs){border-bottom:0}.opportunity-board__tabs :deep(.ui-tabs>button){min-height:48px;flex:1;justify-content:center}.opportunity-board__tabs :deep(.ui-badge){min-width:24px;justify-content:center}@media(max-width:1190px){.board-toolbar :deep(.ui-card__body){align-items:stretch;flex-direction:column}}@media(max-width:680px){.board-toolbar__controls{grid-template-columns:1fr}.board-total{display:none}.board-field--columns{display:none}.opportunity-board__tabs{padding:0}.opportunity-board__tabs :deep(.ui-tabs>button){min-width:max-content;flex:0 0 auto}}
.card-config{margin-bottom:14px}.card-config :deep(.ui-card__body){display:flex;flex-direction:column;gap:18px;padding:16px}.card-config__section h4{margin:0 0 4px;color:var(--ui-text-strong);font-size:.82rem}.card-config__section p{margin:0 0 10px;color:var(--ui-text-subtle);font-size:.7rem}.card-config__checks{display:flex;flex-wrap:wrap;gap:12px}.card-config__checks label{display:flex;align-items:center;gap:6px;color:var(--ui-text);font-size:.75rem}.card-config__checks small{color:var(--ui-text-subtle)}.card-config__max-inline{display:flex;align-items:center;gap:8px;margin-top:12px;color:var(--ui-text);font-size:.75rem}.card-config__max-inline input{width:60px;padding:4px 7px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm)}
</style>
