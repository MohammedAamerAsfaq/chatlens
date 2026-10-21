<!-- eslint-disable vue/block-lang -->
<script setup>
import UiButton from '@/components/ui/UiButton.vue'
import OpportunityCard from './OpportunityCard.vue'

defineProps({
  lane: { type: Object, required: true },
  state: { type: Object, required: true },
  expanded: { type: Boolean, default: false },
})
defineEmits(['load-more', 'open'])
</script>

<template>
  <section
    class="opportunity-lane"
    :class="[`opportunity-lane--${lane.tone}`, { 'is-expanded': expanded }]"
  >
    <header class="opportunity-lane__header">
      <div>
        <p>{{ lane.shortLabel }}</p>
        <h2>{{ lane.label }} <span>{{ state.total }}</span></h2>
        <small>{{ lane.description }}</small>
      </div>
      <i class="opportunity-lane__mark" aria-hidden="true"></i>
    </header>

    <div class="opportunity-lane__body">
      <div v-if="state.loading && !state.rows.length" class="opportunity-lane__empty">Loading records...</div>
      <div v-else-if="state.error" class="opportunity-lane__empty is-error">{{ state.error }}</div>
      <div v-else-if="!state.rows.length" class="opportunity-lane__empty">No opportunities match these filters.</div>
      <OpportunityCard
        v-for="row in state.rows"
        :key="row.id"
        :opportunity="row"
        :lane="lane"
        @open="$emit('open', $event)"
      />
    </div>

    <footer v-if="state.rows.length < state.total" class="opportunity-lane__footer">
      <UiButton size="small" :disabled="state.loading" @click="$emit('load-more', lane)">
        {{ state.loading ? 'Loading...' : `Load more (${state.total - state.rows.length})` }}
      </UiButton>
    </footer>
  </section>
</template>

<style scoped>
.opportunity-lane{--lane-color:#238b75;display:flex;min-width:0;min-height:520px;max-height:calc(100vh - 270px);flex-direction:column;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:color-mix(in srgb,var(--lane-color) 5%,var(--ui-surface));overflow:hidden}.opportunity-lane--selling{--lane-color:#d4862c}.opportunity-lane--lease-inquiry{--lane-color:#3b72c4}.opportunity-lane--lease-offer{--lane-color:#a25f83}.opportunity-lane__header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px;border-bottom:1px solid color-mix(in srgb,var(--lane-color) 24%,var(--ui-border));background:color-mix(in srgb,var(--lane-color) 10%,var(--ui-surface))}.opportunity-lane__header p{margin:0 0 3px;color:var(--lane-color);font-size:.62rem;font-weight:900;letter-spacing:.13em;text-transform:uppercase}.opportunity-lane__header h2{margin:0;color:var(--ui-text-strong);font-size:1rem}.opportunity-lane__header h2 span{display:inline-flex;min-width:24px;height:24px;align-items:center;justify-content:center;margin-left:5px;border-radius:50%;background:var(--ui-surface);color:var(--lane-color);font-size:.7rem}.opportunity-lane__header small{display:block;margin-top:5px;color:var(--ui-text-muted);font-size:.67rem;line-height:1.35}.opportunity-lane__mark{width:9px;height:34px;border-radius:var(--ui-radius-pill);background:var(--lane-color)}.opportunity-lane__body{display:flex;min-height:0;flex:1;flex-direction:column;gap:10px;padding:10px;overflow-y:auto}.opportunity-lane.is-expanded{max-height:calc(100vh - 315px)}.opportunity-lane.is-expanded .opportunity-lane__body{display:grid;grid-template-columns:minmax(0,1fr);align-content:start;padding:12px}.opportunity-lane.is-expanded .opportunity-lane__empty{grid-column:1/-1}.opportunity-lane__empty{display:flex;min-height:160px;align-items:center;justify-content:center;padding:20px;color:var(--ui-text-subtle);font-size:.75rem;text-align:center}.opportunity-lane__empty.is-error{color:var(--ui-danger)}.opportunity-lane__footer{padding:9px;border-top:1px solid var(--ui-border);text-align:center}.opportunity-lane__footer :deep(.ui-button){width:100%}@media(max-width:1190px){.opportunity-lane{max-height:640px}.opportunity-lane.is-expanded{max-height:640px}}@media(max-width:680px){.opportunity-lane{min-height:420px;max-height:620px}}
</style>
