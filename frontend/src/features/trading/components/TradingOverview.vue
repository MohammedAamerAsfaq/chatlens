<script setup>
defineProps({
  stats: { type: Object, default: () => ({}) },
})
</script>

<template>
  <section class="trading-overview" aria-label="Trading activity summary">
    <div class="metric-grid">
      <div class="metric wtb"><strong>{{ stats.today?.wtb_total ?? '—' }}</strong><span>WTB Today</span></div>
      <div class="metric wts"><strong>{{ stats.today?.wts_total ?? '—' }}</strong><span>WTS Today</span></div>
      <div class="metric open"><strong>{{ stats.today?.open ?? '—' }}</strong><span>Open</span></div>
      <div class="metric closed"><strong>{{ stats.today?.closed ?? '—' }}</strong><span>Closed</span></div>
      <div class="metric deal"><strong>{{ stats.today?.deal_done ?? '—' }}</strong><span>Deals Done</span></div>
      <div v-if="stats.avg_response_minutes != null" class="metric neutral"><strong>{{ stats.avg_response_minutes }}m</strong><span>Avg Response</span></div>
      <div v-if="stats.avg_deal_minutes != null" class="metric neutral"><strong>{{ stats.avg_deal_minutes }}m</strong><span>Avg Deal Time</span></div>
    </div>
  </section>
</template>

<style scoped>
.trading-overview{min-width:0;background:var(--ui-surface)}.metric-grid{display:flex;flex-wrap:wrap;gap:6px}.metric{min-width:76px;padding:5px 11px;border-radius:var(--ui-radius-sm);text-align:center}.metric strong,.metric span{display:block}.metric strong{color:var(--ui-text-strong);font-size:1.04rem;line-height:1.1}.metric span{margin-top:2px;color:var(--ui-text-muted);font-size:.61rem;font-weight:700}.metric.wtb{background:var(--ui-success-soft)}.metric.wts{background:var(--ui-warning-soft)}.metric.open{background:var(--ui-warning-soft)}.metric.closed,.metric.neutral{background:var(--ui-surface-muted)}.metric.deal{background:var(--ui-info-soft)}
</style>
