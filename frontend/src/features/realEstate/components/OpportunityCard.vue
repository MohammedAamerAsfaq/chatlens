<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDropdown from '@/components/ui/UiDropdown.vue'
import { statusTone } from '@/features/realEstate/boardOptions'
import { cardFieldsById, defaultCardFieldIds } from '@/features/realEstate/cardFields'
import { title } from '@/features/realEstate/options'

const props = defineProps({
  opportunity: { type: Object, required: true },
  lane: { type: Object, required: true },
  fieldIds: { type: Array, default: () => defaultCardFieldIds },
  actionConfig: { type: Object, default: () => ({ statuses: [], max_inline: 2 }) },
})
defineEmits(['open', 'set-status'])

function fieldValue(id) {
  const field = cardFieldsById[id]
  return field ? field.getValue(props.opportunity) : ''
}

const headerFieldIds = computed(() => props.fieldIds.filter(id => cardFieldsById[id]?.section === 'header'))
const bodyFieldIds = computed(() => props.fieldIds.filter(id => cardFieldsById[id]?.section === 'body'))

const headerTitle = computed(() => {
  const id = headerFieldIds.value[0]
  return (id && fieldValue(id)) || 'Unknown party'
})
const headerSubtitle = computed(() => {
  const parts = headerFieldIds.value.slice(1).map(fieldValue).filter(Boolean)
  return [`#${props.opportunity.id}`, ...parts].join(' · ')
})
const bodyFacts = computed(() => bodyFieldIds.value.map(fieldValue).filter(Boolean))

const inlineStatuses = computed(() => (props.actionConfig.statuses || []).slice(0, props.actionConfig.max_inline ?? 2))
const overflowStatuses = computed(() => (props.actionConfig.statuses || []).slice(props.actionConfig.max_inline ?? 2))
</script>

<template>
  <article class="opportunity-card" :class="`opportunity-card--${lane.tone}`">
    <header class="opportunity-card__header">
      <div class="opportunity-card__party">
        <strong>{{ headerTitle }}</strong>
        <span>{{ headerSubtitle }}</span>
      </div>
      <UiBadge :tone="statusTone(opportunity.status)">{{ title(opportunity.status) }}</UiBadge>
    </header>

    <div class="opportunity-card__body">
      <p class="opportunity-card__summary">
        {{ opportunity.summary || opportunity.original_message || 'No summary available.' }}
      </p>
      <div v-if="bodyFacts.length" class="opportunity-card__facts">
        <span v-for="fact in bodyFacts" :key="fact">{{ fact }}</span>
      </div>
    </div>

    <footer class="opportunity-card__footer">
      <div v-if="inlineStatuses.length || overflowStatuses.length" class="opportunity-card__quick-actions">
        <button
          v-for="status in inlineStatuses" :key="status"
          class="opportunity-card__status-btn" :class="`opportunity-card__status-btn--${statusTone(status)}`"
          @click="$emit('set-status', opportunity, status)"
        >{{ title(status) }}</button>
        <UiDropdown v-if="overflowStatuses.length" align="start">
          <template #trigger>
            <button class="opportunity-card__status-btn" title="More status actions">⋯</button>
          </template>
          <button
            v-for="status in overflowStatuses" :key="status"
            class="opportunity-card__menu-item"
            @click="$emit('set-status', opportunity, status)"
          >{{ title(status) }}</button>
        </UiDropdown>
      </div>
      <UiButton size="small" variant="outline" @click="$emit('open', opportunity)">
        Details
      </UiButton>
    </footer>
  </article>
</template>

<style scoped>
/* flex-shrink:0 guards the lane's non-expanded (flex-column) layout against cards getting
   squeezed below their content height. No overflow:hidden on the card itself - the quick-
   action "More" dropdown pops out below the footer and must not be clipped by its own
   parent; the accent bar below gets its own border-radius instead so it still respects the
   card's rounded corners without needing the parent to clip it. */
.opportunity-card{position:relative;flex-shrink:0;min-height:176px;padding:16px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);box-shadow:var(--ui-shadow-card)}.opportunity-card::before{content:"";position:absolute;inset:0 auto 0 0;width:3px;border-radius:var(--ui-radius-md) 0 0 var(--ui-radius-md);background:var(--lane-color)}.opportunity-card--buying{--lane-color:#238b75}.opportunity-card--selling{--lane-color:#d4862c}.opportunity-card--lease-inquiry{--lane-color:#3b72c4}.opportunity-card--lease-offer{--lane-color:#a25f83}.opportunity-card__header,.opportunity-card__footer{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.opportunity-card__party{min-width:0}.opportunity-card__party strong{display:block;overflow:hidden;color:var(--ui-text-strong);font-size:.82rem;text-overflow:ellipsis;white-space:nowrap}.opportunity-card__party span{display:block;margin-top:3px;overflow:hidden;color:var(--ui-text-subtle);font-size:.67rem;text-overflow:ellipsis;white-space:nowrap}.opportunity-card__summary{display:-webkit-box;min-height:3.4em;margin:14px 0 12px;overflow:hidden;color:var(--ui-text);font-size:.77rem;line-height:1.45;-webkit-box-orient:vertical;-webkit-line-clamp:3}.opportunity-card__facts{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:14px}.opportunity-card__facts span{max-width:100%;padding:4px 7px;border-radius:var(--ui-radius-pill);background:var(--ui-surface-muted);color:var(--ui-text-muted);font-size:.65rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.opportunity-card__footer{align-items:center;flex-wrap:wrap;padding-top:11px;border-top:1px solid var(--ui-border)}.opportunity-card__quick-actions{position:relative;display:flex;flex-wrap:wrap;gap:5px}.opportunity-card__status-btn{padding:5px 9px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface);color:var(--ui-text-muted);font-size:.68rem;font-weight:600;cursor:pointer}.opportunity-card__status-btn:hover{border-color:var(--ui-primary);background:var(--ui-primary-soft);color:var(--ui-primary)}.opportunity-card__status-btn--success{border-color:color-mix(in srgb,var(--ui-success) 35%,var(--ui-border));color:var(--ui-success)}.opportunity-card__status-btn--warning{border-color:color-mix(in srgb,var(--ui-warning) 35%,var(--ui-border));color:var(--ui-warning)}.opportunity-card__status-btn--danger{border-color:color-mix(in srgb,var(--ui-danger) 35%,var(--ui-border));color:var(--ui-danger)}.opportunity-card__status-btn--info{border-color:color-mix(in srgb,var(--ui-info) 35%,var(--ui-border));color:var(--ui-info)}.opportunity-card__quick-actions :deep(.ui-dropdown__menu){position:absolute;top:calc(100% + 4px);z-index:5;display:flex;min-width:140px;flex-direction:column;padding:4px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface);box-shadow:var(--ui-shadow-card)}.opportunity-card__quick-actions :deep(.ui-dropdown__menu--start){left:0}.opportunity-card__menu-item{padding:6px 9px;border:0;border-radius:var(--ui-radius-sm);background:transparent;color:var(--ui-text);font-size:.72rem;text-align:left;cursor:pointer}.opportunity-card__menu-item:hover{background:var(--ui-surface-muted)}
</style>
