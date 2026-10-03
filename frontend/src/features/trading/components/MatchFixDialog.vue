<script setup>
defineProps({ target: { type: Object, default: null }, activeLine: { type: Object, default: null }, drag: { type: Object, required: true }, loading: { type: Boolean, default: false }, error: { type: String, default: '' }, results: { type: Array, default: null }, query: { type: String, default: '' }, products: { type: Array, default: () => [] } })
defineEmits(['close', 'start-drag', 'select-line', 'select-product', 'update:query', 'search'])
</script>

<template>
  <Teleport to="body">
    <div v-if="target" class="dialog-backdrop">
      <section class="match-dialog" :style="{ transform: `translate(${drag.x}px, ${drag.y}px)` }" role="dialog" aria-modal="true">
        <header @mousedown="$emit('start-drag', $event)"><strong>Pick the correct product for "{{ activeLine?.name || '' }}"</strong><button type="button" @mousedown.stop @click="$emit('close')">×</button></header>
        <template v-if="target.lines?.length > 1">
          <div class="section-label">Inquiry lines</div><div class="line-tabs"><button v-for="line in target.lines" :key="line.index" type="button" :class="{ active: activeLine?.index === line.index }" @click="$emit('select-line', line.index)">{{ line.name }}</button></div>
        </template>
        <div v-if="loading" class="state">Searching embeddings…</div><div v-if="error" class="error">{{ error }}</div>
        <template v-if="results?.length"><div class="section-label">Suggested matches</div><div class="product-list"><label v-for="result in results" :key="result.product.id"><input type="checkbox" @change="$emit('select-product', result.product)" /><span>{{ result.product.name }}</span><small v-if="result.product.sale_price">{{ result.product.currency || 'USD' }} {{ result.product.sale_price }}</small><b :class="result.source">{{ result.source === 'direct' ? 'exact' : `~${Math.round((1 - result.distance) * 100)}% match` }}</b></label></div></template>
        <div v-else-if="results && !loading" class="state">No automatic match found — search manually below</div>
        <div class="section-label">Search manually</div><div class="search-row"><input :value="query" autofocus placeholder="Search products…" @input="$emit('update:query', $event.target.value)" /><button type="button" :disabled="loading" @click="$emit('search')">{{ loading ? 'Searching' : 'Search embeddings' }}</button></div>
        <div class="product-list"><label v-for="product in products" :key="product.id"><input type="checkbox" @change="$emit('select-product', product)" /><span>{{ product.name }}</span><small v-if="product.sale_price">{{ product.currency || 'USD' }} {{ product.sale_price }}</small></label><div v-if="!products.length" class="state">No products found</div></div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop{position:fixed;z-index:1200;inset:0;display:grid;place-items:center;padding:20px;background:var(--ui-overlay)}.match-dialog{width:min(620px,95vw);max-height:85vh;overflow:auto;padding:14px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);box-shadow:var(--ui-shadow-popover)}header{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:move;user-select:none}header strong{color:var(--ui-text-strong);font-size:.85rem}header button{border:0;background:transparent;color:var(--ui-text-muted);font-size:1.25rem;cursor:pointer}.section-label{margin-top:10px;color:var(--ui-text-subtle);font-size:.68rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase}.line-tabs{display:flex;flex-wrap:wrap;gap:6px}.line-tabs button,.search-row button{padding:6px 9px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);cursor:pointer}.line-tabs button.active{border-color:var(--ui-primary);background:var(--ui-primary-soft);color:var(--ui-primary)}.state{padding:8px;color:var(--ui-text-muted);font-size:.75rem;text-align:center}.error{padding:6px 8px;border:1px solid color-mix(in srgb,var(--ui-danger) 30%,white);border-radius:var(--ui-radius-xs);background:var(--ui-danger-soft);color:var(--ui-danger);font-size:.75rem}.search-row{display:flex;align-items:center;gap:8px}.search-row input{min-width:0;flex:1;padding:8px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text)}.product-list{display:flex;max-height:280px;flex-direction:column;gap:2px;overflow:auto}.product-list label{display:flex;align-items:center;gap:8px;padding:7px;border-radius:var(--ui-radius-xs);color:var(--ui-text);font-size:.78rem;cursor:pointer}.product-list label:hover{background:var(--ui-surface-muted)}.product-list small{color:var(--ui-text-muted)}.product-list b{margin-left:auto;color:var(--ui-success);font-size:.68rem}.product-list b.embedding{color:var(--ui-info)}
</style>
