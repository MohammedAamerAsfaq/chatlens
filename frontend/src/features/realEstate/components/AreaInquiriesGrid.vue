<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faWhatsapp } from '@fortawesome/free-brands-svg-icons'
import { faArrowUpRightFromSquare, faInbox, faLocationDot, faXmark } from '@fortawesome/free-solid-svg-icons'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { activityColors, opportunityLanes, opportunityStatuses, statusTone } from '@/features/realEstate/boardOptions'
import { useOpportunityWhatsApp } from '@/features/realEstate/composables/useOpportunityWhatsApp'
import TradingConversationDialog from '@/features/trading/components/TradingConversationDialog.vue'
import { formatDateTime } from '@/utils/dateFormat'

// The inquiries behind the Area Map, loaded page by page from the server with the map's
// filters. Choosing an area (bubble or card) narrows the grid to the inquiries in it.
const props = defineProps({
  filters: { type: Object, required: true }, // activity_type, status, date_from, date_to
  area: { type: Object, default: null }, // the selected area row from the area map report
})
const emit = defineEmits(['clear-area'])

const GEO_STATUS_TEXT = { pending: 'Not located yet', error: 'Location failed', unknown: 'No location to go on' }
const laneLabels = Object.fromEntries(opportunityLanes.map(lane => [lane.key, lane.label]))
const statusLabels = Object.fromEntries(opportunityStatuses.map(item => [item.value, item.label]))

// The original WhatsApp message: in a dialog on this page, or in the full Inbox.
const { dialog: waDialog, viewSource, openInInbox } = useOpportunityWhatsApp()
const {
  open: waDialogOpen, loading: waDialogLoading, error: waDialogError, draft: waDialogDraft,
  inquiry: waDialogInquiry, title: waDialogTitle, close: closeWaDialog,
} = waDialog

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = ref(25)
const search = ref('')
const sortKey = ref('first_seen_at')
const sortDirection = ref('desc')

function locationText(location) {
  if (location.status !== 'located') return GEO_STATUS_TEXT[location.status] || location.status
  return [location.sub_area, location.area, location.city].filter(Boolean).join(', ')
}

const columns = [
  { key: 'first_seen_at', label: 'Received', width: '9rem', sortable: true, exportValue: row => formatDateTime(row.first_seen_at) },
  { key: 'activity_type', label: 'Type', width: '9rem', sortable: true, exportValue: row => laneLabels[row.activity_type] || row.activity_type || '' },
  { key: 'summary', label: 'Inquiry', exportValue: row => row.summary || row.original_message },
  { key: 'locations', label: 'Location', width: '15rem', exportValue: row => row.locations.map(locationText).join(' | ') },
  { key: 'contact_name', label: 'Contact', width: '11rem', exportValue: row => [row.contact_name, row.contact_phone].filter(Boolean).join(' ') },
  { key: 'source_chat_name', label: 'Group / chat', width: '11rem', sortable: true, exportValue: row => row.source_chat_name || row.inquiry_medium_name },
  { key: 'status', label: 'Status', width: '7rem', sortable: true, exportValue: row => statusLabels[row.status] || row.status },
  { key: 'open', label: 'Open', width: '6.5rem', exportable: false },
]

const exportFilename = computed(() => `inquiries${props.area ? `-${props.area.name.replace(/[^\w-]+/g, '-').toLowerCase()}` : ''}.csv`)

function requestParams() {
  const params = {
    ...props.filters,
    page: page.value,
    page_size: pageSize.value,
    ordering: `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}`,
  }
  if (props.area) params.area = props.area.id
  if (search.value) params.search = search.value
  return params
}

// Only the newest request may update the grid, so fast clicks between bubbles never show
// an older area's rows.
let requestSeq = 0
async function load() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const { data } = await realEstateApi.areaMapInquiries(requestParams())
    if (seq !== requestSeq) return
    rows.value = data.results
    total.value = data.count
  } catch (exc) {
    if (seq !== requestSeq) return
    rows.value = []
    total.value = 0
    error.value = apiError(exc, 'Unable to load the inquiries.')
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

// Anything that changes which rows match starts again at page 1.
watch(
  [() => JSON.stringify(props.filters), () => props.area?.id, search, pageSize, sortKey, sortDirection],
  () => { if (page.value !== 1) page.value = 1; else load() },
)
watch(page, () => load())
load()

defineExpose({ load })
</script>

<template>
  <section class="area-inquiries">
    <header class="area-inquiries__head">
      <h2>Inquiries</h2>
      <span v-if="area" class="area-inquiries__chip">
        <FontAwesomeIcon :icon="faLocationDot" />
        {{ area.city && area.city !== area.name ? `${area.name}, ${area.city}` : area.name }}
        <button type="button" title="Show inquiries in all areas" aria-label="Clear the area filter" @click="emit('clear-area')"><FontAwesomeIcon :icon="faXmark" /></button>
      </span>
      <small v-else>All areas. Click a bubble or an area card to see the inquiries in it.</small>
    </header>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiDataTable
      v-model:page="page" v-model:page-size="pageSize" v-model:search="search"
      v-model:sort-key="sortKey" v-model:sort-direction="sortDirection"
      :columns="columns" :rows="rows" :total="total" :loading="loading" row-key="id"
      persist-key="real-estate-area-inquiries" :export-filename="exportFilename" expandable
      search-placeholder="Search message, contact, group, property..."
      :empty-title="area ? 'No inquiries in this area match these filters.' : 'No inquiries match these filters.'"
      @refresh="load"
    >
      <template #cell-first_seen_at="{ value }"><span class="area-inquiries__nowrap">{{ formatDateTime(value) }}</span></template>
      <template #cell-activity_type="{ value }">
        <span class="area-inquiries__type"><i :style="{ background: activityColors[value] || 'var(--ui-text-muted)' }"></i>{{ laneLabels[value] || 'Unclassified' }}</span>
      </template>
      <template #cell-summary="{ row }"><span class="area-inquiries__text" :title="row.original_message">{{ row.summary || row.original_message || '-' }}</span></template>
      <template #cell-locations="{ row }">
        <span v-if="!row.locations.length" class="area-inquiries__muted">No property details</span>
        <span
          v-for="location in row.locations" :key="location.sequence"
          :class="['area-inquiries__place', { 'is-match': area && location.area_id === area.id, 'is-off': location.status !== 'located' }]"
        >{{ locationText(location) }}</span>
      </template>
      <template #cell-contact_name="{ row }">
        <span class="area-inquiries__text">{{ row.contact_name || '-' }}</span>
        <small v-if="row.contact_phone" class="area-inquiries__muted">{{ row.contact_phone }}</small>
      </template>
      <template #cell-source_chat_name="{ row }"><span class="area-inquiries__text">{{ row.source_chat_name || row.inquiry_medium_name || '-' }}</span></template>
      <template #cell-status="{ value }"><UiBadge :tone="statusTone(value)">{{ statusLabels[value] || value }}</UiBadge></template>
      <template #cell-open="{ row }">
        <span class="area-inquiries__actions">
          <template v-if="row.source_chat">
            <button type="button" class="area-inquiries__open is-whatsapp" title="View the original WhatsApp message" aria-label="View the original WhatsApp message" @click.stop="viewSource(row)"><FontAwesomeIcon :icon="faWhatsapp" /></button>
            <button type="button" class="area-inquiries__open" title="Open the original message in the WhatsApp Inbox" aria-label="Open the original message in the WhatsApp Inbox" @click.stop="openInInbox(row)"><FontAwesomeIcon :icon="faInbox" /></button>
          </template>
          <RouterLink
            :to="{ name: 'real-estate-opportunity-detail', params: { id: row.id } }" target="_blank"
            class="area-inquiries__open" title="Open the inquiry in a new tab" aria-label="Open the inquiry in a new tab" @click.stop
          ><FontAwesomeIcon :icon="faArrowUpRightFromSquare" /></RouterLink>
        </span>
      </template>
      <template #expanded="{ row }">
        <div class="area-inquiries__detail">
          <div><strong>Message</strong><p>{{ row.original_message || '-' }}</p></div>
          <div v-if="row.locations.length">
            <strong>Properties and where they were placed</strong>
            <ul>
              <li v-for="location in row.locations" :key="location.sequence">
                <span>{{ location.location_raw || `Property ${location.sequence}` }}</span> &rarr; {{ locationText(location) }}
                <small v-if="location.error" class="area-inquiries__error">{{ location.error }}</small>
              </li>
            </ul>
          </div>
        </div>
      </template>
    </UiDataTable>
    <TradingConversationDialog
      :open="waDialogOpen" :title="waDialogTitle" :inquiry="waDialogInquiry"
      :loading="waDialogLoading" :error="waDialogError" :draft="waDialogDraft"
      @close="closeWaDialog"
    />
  </section>
</template>

<style scoped>
.area-inquiries { margin-top:1rem; }
.area-inquiries__head { display:flex; flex-wrap:wrap; align-items:center; gap:.5rem 1rem; margin-bottom:.5rem; }
.area-inquiries__head h2 { margin:0; font-size:1.05rem; }
.area-inquiries__head small, .area-inquiries__muted { color:var(--ui-text-muted); font-size:.8rem; }
.area-inquiries__chip { display:inline-flex; align-items:center; gap:.4rem; padding:.2rem .3rem .2rem .65rem; border:1px solid var(--ui-primary); border-radius:999px; color:var(--ui-primary); font-size:.85rem; font-weight:700; }
.area-inquiries__chip button { display:inline-flex; padding:.2rem .35rem; border:0; border-radius:999px; background:none; color:inherit; cursor:pointer; }
.area-inquiries__chip button:hover { background:var(--ui-surface-muted); }
.area-inquiries__nowrap { white-space:nowrap; }
.area-inquiries__type { display:inline-flex; align-items:center; gap:.4rem; white-space:nowrap; }
.area-inquiries__type i { flex:none; width:10px; height:10px; border-radius:50%; }
.area-inquiries__text { display:-webkit-box; overflow:hidden; -webkit-box-orient:vertical; -webkit-line-clamp:2; line-clamp:2; }
.area-inquiries__muted { display:block; }
.area-inquiries__place { display:block; font-size:.85rem; }
.area-inquiries__place.is-match { color:var(--ui-primary); font-weight:700; }
.area-inquiries__place.is-off { color:var(--ui-text-muted); font-style:italic; }
.area-inquiries__actions { display:inline-flex; align-items:center; gap:.2rem; }
.area-inquiries__open { display:inline-flex; padding:.3rem .35rem; border:0; border-radius:var(--ui-radius-sm); background:none; color:var(--ui-primary); font-size:.95rem; cursor:pointer; }
.area-inquiries__open:hover { background:var(--ui-surface-muted); }
.area-inquiries__open.is-whatsapp { color:#25d366; }
.area-inquiries__detail { display:grid; gap:.75rem; padding:.25rem 0; }
.area-inquiries__detail p { margin:.25rem 0 0; white-space:pre-wrap; }
.area-inquiries__detail ul { margin:.25rem 0 0; padding-left:1.1rem; }
.area-inquiries__error { display:block; color:var(--ui-danger); }
</style>
