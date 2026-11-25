<script setup>
import { computed } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faWhatsapp } from '@fortawesome/free-brands-svg-icons'
import { faArrowUpRightFromSquare, faInbox, faMessage } from '@fortawesome/free-solid-svg-icons'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import { ageLabel, formatDate, moneyRange, opportunityLanes, opportunityParty, statusTone } from '@/features/realEstate/boardOptions'

// Opportunity Search results as rows (the page's other view is cards). The server ranks and
// pages the results; clicking a row opens its details underneath.
const props = defineProps({
  rows: { type: Array, required: true },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  pageSizes: { type: Array, default: () => [10, 20, 50] },
  loading: Boolean,
  showActivity: Boolean,
  emptyTitle: { type: String, default: 'No opportunities match this search.' },
})
const emit = defineEmits(['update:page', 'update:pageSize', 'refresh', 'open', 'view-source', 'open-inbox', 'message-contact'])

const laneLabels = Object.fromEntries(opportunityLanes.map(lane => [lane.key, lane.label]))

function itemDescription(item) {
  return [item.property_type_name || item.property_type_label, item.location_raw].filter(Boolean).join(' - ')
}
function itemRange(item) {
  return moneyRange(item.currency, item.amount_min, item.amount_max)
}
function relevanceTone(value) {
  return value === 'strong' ? 'success' : value === 'possible' ? 'warning' : 'neutral'
}
function score(row) {
  return row.search_score == null ? '' : `${Math.round(row.search_score * 100)}% ${row.search_relevance || ''}`.trim()
}
function firstItem(row) {
  return row.items?.[0] || null
}
function propertiesText(row) {
  const items = row.items || []
  if (!items.length) return ''
  const first = items[0]
  const label = first.title || itemDescription(first) || `Property ${first.sequence}`
  return items.length > 1 ? `${label} +${items.length - 1} more` : label
}

const columns = computed(() => [
  { key: 'party', label: 'Contact', width: '12rem', exportValue: row => opportunityParty(row) },
  { key: 'first_seen_at', label: 'Received', width: '10rem', exportValue: row => `${formatDate(row.first_seen_at)} (${ageLabel(row.first_seen_at)})` },
  ...(props.showActivity ? [{ key: 'activity_type', label: 'Type', width: '8rem', exportValue: row => laneLabels[row.activity_type] || row.activity_type }] : []),
  { key: 'summary', label: 'Inquiry', exportValue: row => row.summary || row.original_message },
  { key: 'properties', label: 'Properties', width: '13rem', exportValue: row => (row.items || []).map(item => item.title || itemDescription(item)).join(' | ') },
  { key: 'price', label: 'Price / budget', width: '10rem', exportValue: row => (row.items || []).map(itemRange).filter(Boolean).join(' | ') },
  { key: 'search_score', label: 'Match', width: '7.5rem', exportValue: score },
  { key: 'status', label: 'Status', width: '6.5rem' },
  { key: 'actions', label: '', width: '8.5rem', exportable: false },
])
</script>

<template>
  <UiDataTable
    class="opportunity-grid"
    :columns="columns" :rows="rows" :total="total" :loading="loading" row-key="id"
    :page="page" :page-size="pageSize" :page-sizes="pageSizes" :searchable="false" expandable
    persist-key="real-estate-opportunity-search" export-filename="opportunity-search.csv" :empty-title="emptyTitle"
    @update:page="emit('update:page', $event)" @update:page-size="emit('update:pageSize', $event)" @refresh="emit('refresh')"
  >
    <template #cell-party="{ row }">
      <strong class="opportunity-grid__party">{{ opportunityParty(row) }}</strong>
      <small class="opportunity-grid__muted">#{{ row.id }}<template v-if="row.duplicate_count > 1"> · {{ row.duplicate_count }} similar</template></small>
    </template>
    <template #cell-first_seen_at="{ row }">
      <span class="opportunity-grid__nowrap">{{ formatDate(row.first_seen_at) }}</span>
      <span v-if="row.first_seen_at" class="opportunity-grid__age">{{ ageLabel(row.first_seen_at) }}</span>
    </template>
    <template #cell-activity_type="{ value }"><UiBadge tone="info">{{ laneLabels[value] || value }}</UiBadge></template>
    <template #cell-summary="{ row }"><span class="opportunity-grid__clamp" :title="row.original_message">{{ row.summary || row.original_message }}</span></template>
    <template #cell-properties="{ row }"><span class="opportunity-grid__clamp">{{ propertiesText(row) || '-' }}</span></template>
    <template #cell-price="{ row }"><span class="opportunity-grid__nowrap">{{ (firstItem(row) && itemRange(firstItem(row))) || '-' }}</span></template>
    <template #cell-search_score="{ row }">
      <UiBadge v-if="row.search_score != null" :tone="relevanceTone(row.search_relevance)">{{ score(row) }}</UiBadge>
      <span v-else class="opportunity-grid__muted">-</span>
    </template>
    <template #cell-status="{ value }"><UiBadge :tone="statusTone(value)">{{ value }}</UiBadge></template>
    <template #cell-actions="{ row }">
      <span class="opportunity-grid__actions" @click.stop @keydown.stop>
        <button v-if="row.source_chat" type="button" class="is-whatsapp" title="View the original WhatsApp message" aria-label="View the original WhatsApp message" @click="emit('view-source', row)"><FontAwesomeIcon :icon="faWhatsapp" /></button>
        <button v-if="row.source_chat" type="button" title="Open the original message in the WhatsApp Inbox" aria-label="Open the original message in the WhatsApp Inbox" @click="emit('open-inbox', row)"><FontAwesomeIcon :icon="faInbox" /></button>
        <button v-if="row.contact" type="button" title="Message this contact directly" aria-label="Message this contact directly" @click="emit('message-contact', row)"><FontAwesomeIcon :icon="faMessage" /></button>
        <button type="button" title="Open the opportunity" aria-label="Open the opportunity" @click="emit('open', row.id)"><FontAwesomeIcon :icon="faArrowUpRightFromSquare" /></button>
      </span>
    </template>
    <template #expanded="{ row }">
      <div class="opportunity-grid__detail">
        <div>
          <strong>Message</strong>
          <p>{{ row.original_message || row.summary || '-' }}</p>
        </div>
        <p v-if="row.search_reasons?.length" class="opportunity-grid__muted">Matched on: {{ row.search_reasons.join(', ') }}</p>
        <div v-if="row.search_adjustments?.length" class="opportunity-grid__adjustments">
          <span v-for="item in row.search_adjustments" :key="item.reason">{{ item.reason }} (-{{ Math.round(item.penalty * 100) }}%)</span>
        </div>
        <div class="opportunity-grid__items">
          <div v-for="item in row.items" :key="item.id" class="opportunity-grid__item">
            <strong>{{ item.title || `Property ${item.sequence}` }}</strong>
            <span>{{ itemDescription(item) || 'Extracted property details' }}</span>
            <span v-if="itemRange(item)">{{ itemRange(item) }}</span>
          </div>
          <span v-if="!row.items?.length" class="opportunity-grid__muted">No extracted property items.</span>
        </div>
        <p v-if="row.contact_phone || row.source_chat_name" class="opportunity-grid__muted">
          <template v-if="row.contact_phone">{{ row.contact_phone }}</template>
          <template v-if="row.contact_phone && row.source_chat_name"> · </template>
          <template v-if="row.source_chat_name">{{ row.source_chat_name }}</template>
        </p>
      </div>
    </template>
  </UiDataTable>
</template>

<style scoped>
.opportunity-grid__party { display:block; }
.opportunity-grid__muted { display:block; color:var(--ui-text-muted); font-size:.85em; }
.opportunity-grid__nowrap { white-space:nowrap; }
.opportunity-grid__age { display:inline-block; margin-top:.15rem; padding:.05rem .45rem; border-radius:999px; background:var(--ui-surface-muted); font-size:.8em; font-weight:700; white-space:nowrap; }
.opportunity-grid__clamp { display:-webkit-box; overflow:hidden; -webkit-box-orient:vertical; -webkit-line-clamp:2; line-clamp:2; }
.opportunity-grid__actions { display:inline-flex; gap:.25rem; }
.opportunity-grid__actions button { display:inline-flex; padding:.35rem .4rem; border:1px solid var(--ui-border); border-radius:var(--ui-radius-sm); background:var(--ui-surface); color:var(--ui-primary); cursor:pointer; }
.opportunity-grid__actions button:hover { border-color:var(--ui-primary); }
.opportunity-grid__actions .is-whatsapp { color:#25d366; }
.opportunity-grid__detail { display:grid; gap:.6rem; padding:.25rem 0; }
.opportunity-grid__detail p { margin:0; white-space:pre-wrap; }
.opportunity-grid__adjustments { display:flex; flex-wrap:wrap; gap:.55rem; color:var(--ui-warning); font-size:.9em; }
.opportunity-grid__items { display:grid; grid-template-columns:repeat(auto-fit,minmax(16rem,1fr)); gap:.5rem; }
.opportunity-grid__item { display:flex; flex-direction:column; gap:.15rem; padding:.6rem; border-radius:calc(var(--ui-radius) - 2px); background:var(--ui-surface-muted); }
.opportunity-grid__item span { color:var(--ui-text-muted); }
</style>
