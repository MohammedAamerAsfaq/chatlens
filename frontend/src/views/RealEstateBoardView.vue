<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import OpportunityDetailModal from '@/features/realEstate/components/OpportunityDetailModal.vue'
import OpportunityLane from '@/features/realEstate/components/OpportunityLane.vue'
import { opportunityLanes, statusFilters } from '@/features/realEstate/boardOptions'
import { apiError } from '@/features/realEstate/apiErrors'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const search = ref('')
const status = ref('')
const activeLaneKey = ref(opportunityLanes[0].key)
const selected = ref(null)
const saving = ref(false)
const globalError = ref('')
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

async function loadLane(lane, append = false) {
  const state = laneStates[lane.key]
  if (append && state.loading) return
  const requestId = state.requestId + 1
  state.requestId = requestId
  state.loading = true
  state.error = ''
  if (!append) state.page = 1
  try {
    const { data } = await realEstateApi.opportunities({
      activity_type: lane.key,
      classification_status: 'classified',
      status: status.value || undefined,
      search: search.value.trim() || undefined,
      page: state.page,
      page_size: 20,
    })
    if (requestId !== state.requestId) return
    const results = data.results || data
    state.rows = append ? [...state.rows, ...results] : results
    state.total = data.count ?? results.length
  } catch (exc) {
    if (requestId === state.requestId) {
      if (append) state.page -= 1
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

function loadMore(lane) {
  laneStates[lane.key].page += 1
  loadLane(lane, true)
}

async function saveStatus(nextStatus) {
  if (!selected.value) return
  saving.value = true
  globalError.value = ''
  try {
    const { data } = await realEstateApi.updateOpportunity(selected.value.id, { status: nextStatus })
    selected.value = data
    const state = laneStates[data.activity_type]
    const index = state?.rows.findIndex(row => row.id === data.id) ?? -1
    if (index >= 0) state.rows[index] = data
  } catch (exc) {
    globalError.value = apiError(exc, 'Unable to update the opportunity status.')
  } finally {
    saving.value = false
  }
}

watch(status, loadAll)
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadAll, 350)
})
onMounted(loadAll)
onBeforeUnmount(() => clearTimeout(searchTimer))
</script>

<template>
  <UiPage width="full">
    <UiPageHeader
      eyebrow="Real Estate Operations"
      title="Opportunity Board"
      description="Work classified property demand and supply through four explicit business lanes."
    >
      <template #actions>
        <div class="board-total"><strong>{{ totalOpportunities }}</strong><span>visible opportunities</span></div>
        <UiButton variant="primary" @click="loadAll">Refresh board</UiButton>
      </template>
    </UiPageHeader>

    <UiNotice v-if="globalError" tone="danger">{{ globalError }}</UiNotice>
    <UiCard class="board-toolbar">
      <div class="board-toolbar__controls">
        <UiInput v-model="search" placeholder="Search party, phone, location, summary, or message...">
          <template #prefix><i class="fa-solid fa-magnifying-glass"></i></template>
        </UiInput>
        <UiSelect v-model="status" :options="statusFilters" />
      </div>
      <p>Only fully classified opportunities are shown. Demand lanes use requirements; supply lanes use reviewable property candidates.</p>
    </UiCard>

    <div class="opportunity-board">
      <div class="opportunity-board__tabs">
        <UiTabs v-model="activeLaneKey" :tabs="laneTabs" />
      </div>
      <OpportunityLane
        :key="activeLane.key"
        :lane="activeLane"
        :state="laneStates[activeLane.key]"
        expanded
        @load-more="loadMore"
        @open="selected = $event"
      />
    </div>

    <OpportunityDetailModal
      :open="Boolean(selected)"
      :opportunity="selected"
      :can-update="canUpdate"
      :busy="saving"
      @close="selected = null"
      @save="saveStatus"
    />
  </UiPage>
</template>

<style scoped>
.board-total{display:flex;align-items:center;gap:8px;padding:7px 11px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface)}.board-total strong{color:var(--ui-primary);font-size:1rem}.board-total span{color:var(--ui-text-muted);font-size:.68rem}.board-toolbar{margin-bottom:14px}.board-toolbar :deep(.ui-card__body){display:flex;align-items:center;justify-content:space-between;gap:18px;padding:12px}.board-toolbar__controls{display:grid;grid-template-columns:minmax(260px,520px) 190px;gap:10px;flex:1}.board-toolbar p{max-width:500px;margin:0;color:var(--ui-text-subtle);font-size:.68rem;line-height:1.4}.opportunity-board{min-width:0}.opportunity-board__tabs{margin-bottom:12px;padding:0 8px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.opportunity-board__tabs :deep(.ui-tabs){border-bottom:0}.opportunity-board__tabs :deep(.ui-tabs>button){min-height:48px;flex:1;justify-content:center}.opportunity-board__tabs :deep(.ui-badge){min-width:24px;justify-content:center}@media(max-width:1190px){.board-toolbar :deep(.ui-card__body){align-items:stretch;flex-direction:column}.board-toolbar p{max-width:none}}@media(max-width:680px){.board-toolbar__controls{grid-template-columns:1fr}.board-total{display:none}.opportunity-board__tabs{padding:0}.opportunity-board__tabs :deep(.ui-tabs>button){min-width:max-content;flex:0 0 auto}}
</style>
