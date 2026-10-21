<!-- eslint-disable vue/block-lang -->
<script setup>
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import {
  formatDate, opportunityFacts, opportunityParty, statusTone,
} from '@/features/realEstate/boardOptions'
import { title } from '@/features/realEstate/options'

defineProps({
  opportunity: { type: Object, required: true },
  lane: { type: Object, required: true },
})
defineEmits(['open'])
</script>

<template>
  <article class="opportunity-card" :class="`opportunity-card--${lane.tone}`">
    <header>
      <div class="opportunity-card__party">
        <strong>{{ opportunityParty(opportunity) }}</strong>
        <span>#{{ opportunity.id }} · {{ formatDate(opportunity.first_seen_at) }}</span>
      </div>
      <UiBadge :tone="statusTone(opportunity.status)">{{ title(opportunity.status) }}</UiBadge>
    </header>

    <p class="opportunity-card__summary">
      {{ opportunity.summary || opportunity.original_message || 'No summary available.' }}
    </p>

    <div v-if="opportunityFacts(opportunity).length" class="opportunity-card__facts">
      <span v-for="fact in opportunityFacts(opportunity)" :key="fact">{{ fact }}</span>
    </div>

    <footer>
      <div class="opportunity-card__source">
        <span>{{ opportunity.source_chat_name || 'Direct message' }}</span>
        <small>{{ opportunity.account_name || 'Unassigned account' }}</small>
      </div>
      <UiButton size="small" variant="outline" @click="$emit('open', opportunity)">
        Details
      </UiButton>
    </footer>
  </article>
</template>

<style scoped>
.opportunity-card{position:relative;min-height:176px;padding:16px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);box-shadow:var(--ui-shadow-card);overflow:hidden}.opportunity-card::before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:var(--lane-color)}.opportunity-card--buying{--lane-color:#238b75}.opportunity-card--selling{--lane-color:#d4862c}.opportunity-card--lease-inquiry{--lane-color:#3b72c4}.opportunity-card--lease-offer{--lane-color:#a25f83}.opportunity-card header,.opportunity-card footer{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.opportunity-card__party{min-width:0}.opportunity-card__party strong{display:block;overflow:hidden;color:var(--ui-text-strong);font-size:.82rem;text-overflow:ellipsis;white-space:nowrap}.opportunity-card__party span,.opportunity-card__source small{display:block;margin-top:3px;color:var(--ui-text-subtle);font-size:.67rem}.opportunity-card__summary{display:-webkit-box;min-height:3.4em;margin:14px 0 12px;overflow:hidden;color:var(--ui-text);font-size:.77rem;line-height:1.45;-webkit-box-orient:vertical;-webkit-line-clamp:3}.opportunity-card__facts{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:14px}.opportunity-card__facts span{max-width:100%;padding:4px 7px;border-radius:var(--ui-radius-pill);background:var(--ui-surface-muted);color:var(--ui-text-muted);font-size:.65rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.opportunity-card footer{align-items:center;padding-top:11px;border-top:1px solid var(--ui-border)}.opportunity-card__source{min-width:0}.opportunity-card__source span{display:block;max-width:360px;overflow:hidden;color:var(--ui-text-muted);font-size:.7rem;font-weight:700;text-overflow:ellipsis;white-space:nowrap}
</style>
