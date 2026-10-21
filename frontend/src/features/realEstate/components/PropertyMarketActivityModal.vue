<script setup>
import { computed } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiModal from '@/components/ui/UiModal.vue'
import { title } from '@/features/realEstate/options'

const props = defineProps({
  open: { type: Boolean, default: false },
  property: { type: Object, default: null },
  activity: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})
defineEmits(['close'])

const lanes = [
  ['buying', 'Buying'], ['selling', 'Selling'],
  ['leasing_inquiry', 'Leasing inquiries'], ['leasing_offer', 'Leasing offers'],
]
const subtitle = computed(() => `${props.activity?.total || 0} linked market appearances`)
function shortDate(value) {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '-'
}
</script>

<template>
  <UiModal :open="open" :title="`${property?.title || 'Property'} activity`" :subtitle="subtitle" size="large" tall @close="$emit('close')">
    <p v-if="loading" class="market-activity__empty">Loading market activity...</p>
    <div v-else class="market-activity">
      <section class="market-activity__counts">
        <article v-for="lane in lanes" :key="lane[0]"><strong>{{ activity?.counts?.[lane[0]] || 0 }}</strong><span>{{ lane[1] }}</span></article>
      </section>
      <section class="market-activity__events">
        <header><h3>Recent opportunities</h3><p>Every row is an extracted market event linked to this physical property.</p></header>
        <div v-if="activity?.recent?.length" class="market-activity__list">
          <article v-for="event in activity.recent" :key="event.item_id">
            <div><strong>{{ event.party }}</strong><p>{{ event.summary || 'No summary available.' }}</p></div>
            <div class="market-activity__meta"><UiBadge tone="neutral">{{ title(event.activity_type) }}</UiBadge><span>{{ shortDate(event.first_seen_at) }}</span></div>
          </article>
        </div>
        <p v-else class="market-activity__empty">No opportunities are linked to this property yet.</p>
      </section>
    </div>
  </UiModal>
</template>

<style scoped>
.market-activity{display:grid;gap:16px}.market-activity__counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.market-activity__counts article{padding:16px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}.market-activity__counts strong,.market-activity__counts span{display:block}.market-activity__counts strong{font-size:1.3rem;color:var(--ui-text-strong)}.market-activity__counts span{margin-top:4px;color:var(--ui-text-muted);font-size:.7rem}.market-activity__events{border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);overflow:hidden}.market-activity__events>header{padding:15px;border-bottom:1px solid var(--ui-border)}.market-activity__events h3,.market-activity__events p{margin:0}.market-activity__events header p{margin-top:4px;color:var(--ui-text-muted);font-size:.7rem}.market-activity__list{max-height:430px;overflow:auto}.market-activity__list article{display:flex;justify-content:space-between;gap:16px;padding:13px 15px;border-bottom:1px solid var(--ui-border)}.market-activity__list article:last-child{border-bottom:0}.market-activity__list strong{font-size:.76rem}.market-activity__list p{margin-top:4px;color:var(--ui-text-muted);font-size:.7rem}.market-activity__meta{display:flex;align-items:flex-end;flex-direction:column;gap:6px;white-space:nowrap}.market-activity__meta span{color:var(--ui-text-subtle);font-size:.65rem}.market-activity__empty{padding:30px;text-align:center;color:var(--ui-text-muted)}@media(max-width:720px){.market-activity__counts{grid-template-columns:1fr 1fr}.market-activity__list article{flex-direction:column}.market-activity__meta{align-items:flex-start}}
</style>
