<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import {
  formatDate, money, opportunityParty, opportunityStatuses, statusTone,
} from '@/features/realEstate/boardOptions'
import { title } from '@/features/realEstate/options'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canUpdate = computed(() => auth.hasPermission('real_estate.opportunities.update'))

const opportunity = ref(null)
const properties = ref([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const status = ref('new')
const selections = ref({})

const propertyOptions = computed(() => properties.value.map(item => ({
  value: item.id, label: `${item.title}${item.reference_code ? ` (${item.reference_code})` : ''}`,
})))

function values(value) {
  if (!Array.isArray(value) || !value.length) return '-'
  return value.join(', ')
}

function range(low, high, suffix = '') {
  if (low == null && high == null) return '-'
  if (low != null && high != null && low !== high) return `${low} to ${high}${suffix}`
  return `${low ?? high}${suffix}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await realEstateApi.getOpportunity(route.params.id)
    opportunity.value = data
    status.value = data.status || 'new'
    selections.value = Object.fromEntries((data.items || []).map(item => [item.id, item.property || '']))
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load this opportunity.')
  } finally {
    loading.value = false
  }
}

async function loadProperties() {
  try {
    const { data } = await realEstateApi.properties({ page_size: 100, ordering: 'title' })
    properties.value = data.results || data
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load properties for matching.')
  }
}

async function saveStatus() {
  if (!opportunity.value) return
  busy.value = true
  error.value = ''
  try {
    const { data } = await realEstateApi.updateOpportunity(opportunity.value.id, { status: status.value })
    opportunity.value = data
  } catch (exc) {
    error.value = apiError(exc, 'Unable to update the opportunity status.')
  } finally {
    busy.value = false
  }
}

function replaceItem(updated) {
  opportunity.value.items = opportunity.value.items.map(item => item.id === updated.id ? updated : item)
}

async function itemAction(action, item, propertyId = null) {
  busy.value = true
  error.value = ''
  try {
    let response
    if (action === 'link') response = await realEstateApi.linkOpportunityItem(item.id, propertyId)
    else if (action === 'unlink') response = await realEstateApi.unlinkOpportunityItem(item.id)
    else response = await realEstateApi.createPropertyFromOpportunityItem(item.id)
    replaceItem(response.data.item || response.data)
    if (action === 'create') await loadProperties()
  } catch (exc) {
    error.value = apiError(exc, 'Unable to update the property link.')
  } finally {
    busy.value = false
  }
}

onMounted(() => Promise.all([load(), loadProperties()]))
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader
      eyebrow="Real Estate Operations"
      :title="opportunity ? `${title(opportunity.activity_type)} #${opportunity.id}` : 'Opportunity'"
      :description="opportunity ? opportunityParty(opportunity) : 'Loading opportunity details...'"
    >
      <template #actions>
        <UiButton @click="router.push({ name: 'real-estate-board' })">Back to board</UiButton>
      </template>
    </UiPageHeader>

    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <div v-if="loading && !opportunity" class="opportunity-detail__loading">Loading…</div>

    <div v-else-if="opportunity" class="opportunity-detail">
      <section class="opportunity-detail__hero">
        <div>
          <UiBadge :tone="statusTone(opportunity.status)">{{ title(opportunity.status) }}</UiBadge>
          <h3>{{ opportunity.summary || 'No summary available.' }}</h3>
          <p>{{ opportunity.original_message || 'Original message is unavailable.' }}</p>
        </div>
        <dl>
          <div><dt>Received</dt><dd>{{ formatDate(opportunity.first_seen_at) }}</dd></div>
          <div><dt>Medium</dt><dd>{{ opportunity.inquiry_medium_name || 'WhatsApp' }}</dd></div>
          <div><dt>Party</dt><dd>{{ opportunityParty(opportunity) }}</dd></div>
          <div><dt>Contact</dt><dd>{{ opportunity.contact_phone || '-' }}</dd></div>
          <div><dt>Source</dt><dd>{{ opportunity.source_chat_name || opportunity.source_reference || 'Manual entry' }}</dd></div>
          <div v-if="opportunity.source_reference"><dt>Reference</dt><dd>{{ opportunity.source_reference }}</dd></div>
          <div><dt>Account</dt><dd>{{ opportunity.account_name || '-' }}</dd></div>
          <div><dt>Assigned</dt><dd>{{ opportunity.assigned_to_name || 'Unassigned' }}</dd></div>
        </dl>
      </section>

      <section v-if="opportunity.items?.length" class="opportunity-items">
        <article v-for="item in opportunity.items" :key="item.id" class="opportunity-item">
          <header>
            <div><small>Property item {{ item.sequence }}</small><h4>{{ item.title || item.property_type_name || 'Extracted property details' }}</h4></div>
            <UiBadge :tone="item.match_status === 'linked' ? 'success' : item.match_status === 'suggested' ? 'warning' : 'neutral'">{{ title(item.match_status) }}</UiBadge>
          </header>
          <div class="opportunity-detail__grid">
            <div><span>Location</span><strong>{{ item.location_raw || values(item.locations) }}</strong></div>
            <div><span>Property type</span><strong>{{ item.property_type_name || title(item.property_type_label || 'other') }}</strong></div>
            <div><span>Bedrooms</span><strong>{{ range(item.bedrooms_min, item.bedrooms_max) }}</strong></div>
            <div><span>Area</span><strong>{{ range(item.area_min, item.area_max, ` ${item.area_unit}`) }}</strong></div>
            <div><span>{{ title(item.amount_role) }}</span><strong>{{ money(item.currency, item.amount_min) || '-' }}<template v-if="item.amount_max && item.amount_max !== item.amount_min"> to {{ Number(item.amount_max).toLocaleString() }}</template></strong></div>
            <div><span>Timeframe</span><strong>{{ item.timeframe || '-' }}</strong></div>
          </div>
          <div v-if="canUpdate" class="opportunity-item__actions">
            <template v-if="item.match_status === 'linked'">
              <strong>Linked to {{ item.property_title }}</strong>
              <UiButton size="small" variant="outline" :disabled="busy" @click="itemAction('unlink', item)">Unlink</UiButton>
            </template>
            <template v-else>
              <UiSelect v-model="selections[item.id]" :options="propertyOptions" placeholder="Select an existing property" />
              <UiButton size="small" variant="primary" :disabled="busy || !selections[item.id]" @click="itemAction('link', item, selections[item.id])">Link property</UiButton>
              <UiButton v-if="item.item_kind === 'supply'" size="small" variant="outline" :disabled="busy" @click="itemAction('create', item)">Create property</UiButton>
            </template>
          </div>
        </article>
      </section>
      <section v-else class="opportunity-detail__missing">Classification is complete, but no property item was extracted.</section>

      <section v-if="canUpdate" class="opportunity-detail__workflow">
        <div><label>Workflow status</label><UiSelect v-model="status" :options="opportunityStatuses" /></div>
        <UiButton variant="primary" :disabled="busy || status === opportunity.status" @click="saveStatus">
          {{ busy ? 'Saving...' : 'Update status' }}
        </UiButton>
      </section>
    </div>
  </UiPage>
</template>

<style scoped>
.opportunity-detail__loading{padding:40px;color:var(--ui-text-subtle);font-size:.8rem;text-align:center}
.opportunity-detail{display:grid;gap:16px}.opportunity-detail__hero{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(230px,.7fr);gap:20px;padding:18px;border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}.opportunity-detail__hero h3{margin:12px 0 7px;color:var(--ui-text-strong);font-size:1.05rem}.opportunity-detail__hero p{margin:0;color:var(--ui-text-muted);font-size:.78rem;line-height:1.55;white-space:pre-wrap}.opportunity-detail dl{display:grid;gap:8px;margin:0}.opportunity-detail dl div{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--ui-border);padding-bottom:7px}.opportunity-detail dt{color:var(--ui-text-subtle);font-size:.68rem}.opportunity-detail dd{margin:0;color:var(--ui-text);font-size:.7rem;font-weight:700;text-align:right}.opportunity-items{display:grid;gap:12px}.opportunity-item{padding:14px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.opportunity-item>header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}.opportunity-item h4{margin:3px 0 0;color:var(--ui-text-strong);font-size:.86rem}.opportunity-item small{color:var(--ui-text-subtle);font-size:.64rem;text-transform:uppercase}.opportunity-detail__grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.opportunity-detail__grid div{min-width:0;padding:13px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm)}.opportunity-detail__grid span{display:block;margin-bottom:5px;color:var(--ui-text-subtle);font-size:.64rem;text-transform:uppercase}.opportunity-detail__grid strong{display:block;color:var(--ui-text);font-size:.75rem;overflow-wrap:anywhere}.opportunity-item__actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--ui-border)}.opportunity-item__actions :deep(.choices){width:min(360px,100%);margin:0}.opportunity-item__actions>strong{margin-right:auto;color:var(--ui-success);font-size:.73rem}.opportunity-detail__missing{padding:18px;border:1px dashed var(--ui-border-strong);border-radius:var(--ui-radius-md);color:var(--ui-text-muted);font-size:.75rem;text-align:center}.opportunity-detail__workflow{display:flex;align-items:flex-end;justify-content:flex-end;gap:10px;padding-top:14px;border-top:1px solid var(--ui-border)}.opportunity-detail__workflow>div{width:260px}.opportunity-detail__workflow label{display:block;margin-bottom:6px;color:var(--ui-text-muted);font-size:.7rem;font-weight:800}@media(max-width:720px){.opportunity-detail__hero{grid-template-columns:1fr}.opportunity-detail__grid{grid-template-columns:1fr 1fr}.opportunity-item__actions{align-items:stretch;flex-direction:column}.opportunity-item__actions :deep(.choices){width:100%}.opportunity-detail__workflow{align-items:stretch;flex-direction:column}.opportunity-detail__workflow>div{width:100%}}@media(max-width:480px){.opportunity-detail__grid{grid-template-columns:1fr}}
</style>
