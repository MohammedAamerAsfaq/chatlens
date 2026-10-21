<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed, ref, watch } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import {
  formatDate, money, opportunityParty, opportunityStatuses, statusTone,
} from '@/features/realEstate/boardOptions'
import { title } from '@/features/realEstate/options'

const props = defineProps({
  open: { type: Boolean, default: false },
  opportunity: { type: Object, default: null },
  canUpdate: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'save'])
const status = ref('new')
const detail = computed(() => props.opportunity?.requirement || props.opportunity?.property_candidate || null)
watch(() => props.opportunity, value => { status.value = value?.status || 'new' }, { immediate: true })

function values(value) {
  if (!Array.isArray(value) || !value.length) return '-'
  return value.join(', ')
}
</script>

<template>
  <UiModal
    :open="open"
    :title="opportunity ? `${title(opportunity.activity_type)} #${opportunity.id}` : 'Opportunity'"
    :subtitle="opportunity ? opportunityParty(opportunity) : ''"
    size="large"
    tall
    @close="$emit('close')"
  >
    <div v-if="opportunity" class="opportunity-detail">
      <section class="opportunity-detail__hero">
        <div>
          <UiBadge :tone="statusTone(opportunity.status)">{{ title(opportunity.status) }}</UiBadge>
          <h3>{{ opportunity.summary || 'No summary available.' }}</h3>
          <p>{{ opportunity.original_message || 'Original message is unavailable.' }}</p>
        </div>
        <dl>
          <div><dt>Received</dt><dd>{{ formatDate(opportunity.first_seen_at) }}</dd></div>
          <div><dt>Source</dt><dd>{{ opportunity.source_chat_name || 'Direct message' }}</dd></div>
          <div><dt>Account</dt><dd>{{ opportunity.account_name || '-' }}</dd></div>
          <div><dt>Assigned</dt><dd>{{ opportunity.assigned_to_name || 'Unassigned' }}</dd></div>
        </dl>
      </section>

      <section v-if="opportunity.requirement" class="opportunity-detail__grid">
        <div><span>Locations</span><strong>{{ values(detail.acceptable_locations) }}</strong></div>
        <div><span>Property types</span><strong>{{ values(detail.acceptable_property_types) }}</strong></div>
        <div><span>Bedrooms</span><strong>{{ detail.bedrooms_min ?? '-' }} to {{ detail.bedrooms_max ?? '-' }}</strong></div>
        <div><span>Budget</span><strong>{{ money(detail.currency, detail.budget_min) || '-' }} to {{ money(detail.currency, detail.budget_max) || '-' }}</strong></div>
        <div><span>Area</span><strong>{{ detail.area_min ?? '-' }} to {{ detail.area_max ?? '-' }} {{ detail.area_unit }}</strong></div>
        <div><span>Timeframe</span><strong>{{ detail.timeframe || '-' }}</strong></div>
      </section>

      <section v-else-if="opportunity.property_candidate" class="opportunity-detail__grid">
        <div><span>Candidate</span><strong>{{ detail.title || `Candidate #${detail.id}` }}</strong></div>
        <div><span>Property type</span><strong>{{ title(detail.property_type || 'other') }}</strong></div>
        <div><span>Location</span><strong>{{ detail.location_raw || '-' }}</strong></div>
        <div><span>Bedrooms</span><strong>{{ detail.bedrooms ?? '-' }}</strong></div>
        <div><span>Area</span><strong>{{ detail.area ?? '-' }} {{ detail.area_unit }}</strong></div>
        <div><span>Asking price</span><strong>{{ money(detail.currency, detail.asking_price) || '-' }}</strong></div>
      </section>

      <section v-else class="opportunity-detail__missing">
        Classification is complete, but the extracted requirement or offer record is not available yet.
      </section>

      <section v-if="canUpdate" class="opportunity-detail__workflow">
        <div><label>Workflow status</label><UiSelect v-model="status" :options="opportunityStatuses" /></div>
        <UiButton variant="primary" :disabled="busy || status === opportunity.status" @click="emit('save', status)">
          {{ busy ? 'Saving...' : 'Update status' }}
        </UiButton>
      </section>
    </div>
  </UiModal>
</template>

<style scoped>
.opportunity-detail{display:grid;gap:16px}.opportunity-detail__hero{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(230px,.7fr);gap:20px;padding:18px;border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}.opportunity-detail__hero h3{margin:12px 0 7px;color:var(--ui-text-strong);font-size:1.05rem}.opportunity-detail__hero p{margin:0;color:var(--ui-text-muted);font-size:.78rem;line-height:1.55;white-space:pre-wrap}.opportunity-detail dl{display:grid;gap:8px;margin:0}.opportunity-detail dl div{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--ui-border);padding-bottom:7px}.opportunity-detail dt{color:var(--ui-text-subtle);font-size:.68rem}.opportunity-detail dd{margin:0;color:var(--ui-text);font-size:.7rem;font-weight:700;text-align:right}.opportunity-detail__grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.opportunity-detail__grid div{min-width:0;padding:13px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm)}.opportunity-detail__grid span{display:block;margin-bottom:5px;color:var(--ui-text-subtle);font-size:.64rem;text-transform:uppercase}.opportunity-detail__grid strong{display:block;color:var(--ui-text);font-size:.75rem;overflow-wrap:anywhere}.opportunity-detail__missing{padding:18px;border:1px dashed var(--ui-border-strong);border-radius:var(--ui-radius-md);color:var(--ui-text-muted);font-size:.75rem;text-align:center}.opportunity-detail__workflow{display:flex;align-items:flex-end;justify-content:flex-end;gap:10px;padding-top:14px;border-top:1px solid var(--ui-border)}.opportunity-detail__workflow>div{width:260px}.opportunity-detail__workflow label{display:block;margin-bottom:6px;color:var(--ui-text-muted);font-size:.7rem;font-weight:800}@media(max-width:720px){.opportunity-detail__hero{grid-template-columns:1fr}.opportunity-detail__grid{grid-template-columns:1fr 1fr}.opportunity-detail__workflow{align-items:stretch;flex-direction:column}.opportunity-detail__workflow>div{width:100%}}@media(max-width:480px){.opportunity-detail__grid{grid-template-columns:1fr}}
</style>
