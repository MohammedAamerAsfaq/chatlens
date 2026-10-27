<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed } from 'vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import OpportunityCard from './OpportunityCard.vue'

const props = defineProps({
  lane: { type: Object, required: true },
  state: { type: Object, required: true },
  expanded: { type: Boolean, default: false },
  columns: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  fieldIds: { type: Array, default: undefined },
  actionConfig: { type: Object, default: undefined },
})
defineEmits(['change-page', 'open', 'set-status', 'view-source'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.state.total / props.pageSize)))
</script>

<template>
  <section
    class="opportunity-lane"
    :class="[`opportunity-lane--${lane.tone}`, { 'is-expanded': expanded }]"
    :style="{ '--lane-columns': columns }"
  >
    <div class="opportunity-lane__body">
      <div v-if="state.loading && !state.rows.length" class="opportunity-lane__empty">Loading records...</div>
      <div v-else-if="state.error" class="opportunity-lane__empty is-error">{{ state.error }}</div>
      <div v-else-if="!state.rows.length" class="opportunity-lane__empty">No opportunities match these filters.</div>
      <OpportunityCard
        v-for="row in state.rows"
        :key="row.id"
        :opportunity="row"
        :lane="lane"
        :field-ids="fieldIds"
        :action-config="actionConfig"
        @open="$emit('open', $event)"
        @set-status="(opportunity, status) => $emit('set-status', opportunity, status)"
        @view-source="$emit('view-source', $event)"
      />
    </div>

    <footer v-if="state.total > 0" class="opportunity-lane__footer">
      <UiPagination :page="state.page" :pages="totalPages" @change="page => $emit('change-page', lane, page)" />
    </footer>
  </section>
</template>

<style scoped>
.opportunity-lane{--lane-color:#238b75;display:flex;min-width:0;min-height:520px;max-height:calc(100vh - 270px);flex-direction:column;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:color-mix(in srgb,var(--lane-color) 5%,var(--ui-surface));overflow:hidden}.opportunity-lane--selling{--lane-color:#d4862c}.opportunity-lane--lease-inquiry{--lane-color:#3b72c4}.opportunity-lane--lease-offer{--lane-color:#a25f83}.opportunity-lane__body{display:flex;min-height:0;flex:1;flex-direction:column;gap:10px;padding:10px;overflow-y:auto}/* Expanded (single-lane board) mode deliberately has no max-height/scroll trap - the lane
   grows to fit every card and the page itself scrolls, so nothing ever looks clipped at a
   fixed pixel boundary the way a bounded inner-scroll panel did. */
.opportunity-lane.is-expanded{max-height:none;overflow:visible}.opportunity-lane.is-expanded .opportunity-lane__body{display:grid;grid-template-columns:repeat(var(--lane-columns,1),minmax(0,1fr));align-content:start;overflow-y:visible;padding:12px}.opportunity-lane.is-expanded .opportunity-lane__empty{grid-column:1/-1}.opportunity-lane__empty{display:flex;min-height:160px;align-items:center;justify-content:center;padding:20px;color:var(--ui-text-subtle);font-size:.75rem;text-align:center}.opportunity-lane__empty.is-error{color:var(--ui-danger)}.opportunity-lane__footer{padding:9px;border-top:1px solid var(--ui-border)}.opportunity-lane__footer :deep(.ui-pagination){margin-top:0;justify-content:center}@media(max-width:1190px){.opportunity-lane:not(.is-expanded){max-height:640px}.opportunity-lane.is-expanded .opportunity-lane__body{grid-template-columns:repeat(min(var(--lane-columns,1),2),minmax(0,1fr))}}@media(max-width:680px){.opportunity-lane:not(.is-expanded){min-height:420px;max-height:620px}.opportunity-lane.is-expanded .opportunity-lane__body{grid-template-columns:minmax(0,1fr)}}
</style>
