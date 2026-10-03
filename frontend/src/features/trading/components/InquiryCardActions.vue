<script setup>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faMessage } from '@fortawesome/free-solid-svg-icons'

const props = defineProps({
  inquiry: { type: Object, required: true },
  manualMatchAvailable: { type: Boolean, default: false },
  waLink: { type: String, default: '' },
  askPriceLink: { type: String, default: '' },
  priceListLink: { type: String, default: '' },
  priceListEnabled: { type: Boolean, default: false },
  formattedPriceListAvailable: { type: Boolean, default: false },
})

const emit = defineEmits([
  'inquiry-products', 'manual-match', 'market-parties', 'wa-chatlens', 'wa-direct-chatlens',
  'chat-reference', 'ask-price-chatlens', 'ask-price-direct-chatlens',
  'price-list-chatlens', 'price-list-direct-chatlens',
])

function closeMenu(event) {
  event.currentTarget?.closest('details')?.removeAttribute('open')
}

function run(event, action) {
  closeMenu(event)
  emit(action)
}
</script>

<template>
  <div class="inquiry-card-actions">
    <details v-if="inquiry.products?.length || manualMatchAvailable" class="action-menu products-menu">
      <summary class="action-button products">Inquiry Products <span aria-hidden="true">▾</span></summary>
      <div class="action-menu-items">
        <button v-if="inquiry.products?.length" type="button" @click="run($event, 'inquiry-products')">Inquiry Product List</button>
        <button v-if="manualMatchAvailable" type="button" @click="run($event, 'manual-match')">Manual Match</button>
      </div>
    </details>

    <button v-if="inquiry.products?.length" type="button" class="action-button market" @click="$emit('market-parties')">
      {{ inquiry.inquiry_type === 'sell' ? 'Potential Buyers' : 'Available Sellers' }}
    </button>

    <details v-if="inquiry.source_chat_id || waLink" class="action-menu wa-menu">
      <summary class="action-button wa" title="WhatsApp actions">
        <svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zm4.82 13.68c-.2.56-1.18 1.07-1.62 1.14-.44.07-.98.1-1.58-.1-.36-.12-.83-.28-1.42-.55-2.5-1.08-4.13-3.6-4.26-3.77-.13-.17-1.05-1.4-1.05-2.67 0-1.27.66-1.9.9-2.16.23-.26.5-.32.67-.32.17 0 .33 0 .48.01.15.01.36-.06.56.43.2.49.7 1.7.76 1.82.06.13.1.27.02.43-.08.17-.12.27-.23.41-.11.14-.24.31-.33.42-.11.13-.23.27-.1.53.13.26.59 1 1.27 1.63.87.8 1.61 1.04 1.87 1.16.26.12.41.1.57-.06.16-.16.66-.77.83-1.04.17-.26.34-.22.57-.13.23.09 1.44.68 1.69.8.25.12.41.18.47.28.07.1.07.56-.13 1.12z" /></svg>
        WA <span aria-hidden="true">▾</span>
      </summary>
      <div class="action-menu-items">
        <a v-if="waLink" :href="waLink" @click="closeMenu">WA Client</a>
        <button v-if="inquiry.source_chat_id" type="button" @click="run($event, 'wa-chatlens')">WA ChatLens</button>
        <button v-if="inquiry.contact" type="button" @click="run($event, 'wa-direct-chatlens')">ChatLens <FontAwesomeIcon :icon="faMessage" /></button>
        <button v-if="inquiry.source_chat_id" type="button" @click="run($event, 'chat-reference')">Chat Ref</button>
      </div>
    </details>

    <details v-if="askPriceLink || inquiry.source_chat_id || (priceListEnabled && priceListLink)" class="action-menu prices-menu">
      <summary class="action-button prices">Prices <span aria-hidden="true">▾</span></summary>
      <div class="action-menu-items">
        <a v-if="askPriceLink" :href="askPriceLink" @click="closeMenu">Ask Price - WA Client</a>
        <button v-if="inquiry.source_chat_id" type="button" @click="run($event, 'ask-price-chatlens')">Ask Price - ChatLens</button>
        <button v-if="inquiry.contact" type="button" @click="run($event, 'ask-price-direct-chatlens')">Ask Price - ChatLens <FontAwesomeIcon :icon="faMessage" /></button>
        <template v-if="priceListEnabled">
          <a v-if="priceListLink" :href="priceListLink" @click="closeMenu">Price List - WA Client</a>
          <button v-if="inquiry.source_chat_id && formattedPriceListAvailable" type="button" @click="run($event, 'price-list-chatlens')">Price List - ChatLens</button>
          <button v-if="inquiry.contact && formattedPriceListAvailable" type="button" @click="run($event, 'price-list-direct-chatlens')">Price List - ChatLens <FontAwesomeIcon :icon="faMessage" /></button>
        </template>
      </div>
    </details>
  </div>
</template>

<style scoped>
.inquiry-card-actions{display:flex;align-items:center;gap:6px}.action-button{padding:4px 12px;border:0;border-radius:var(--ui-radius-sm);cursor:pointer;font:600 .8rem var(--ui-font-sans)}.action-menu{position:relative}.action-menu>summary{display:flex;align-items:center;gap:5px;list-style:none;user-select:none}.action-menu>summary::-webkit-details-marker{display:none}.products{background:#eef2ff;color:#3730a3}.products-menu[open]>.products{background:#e0e7ff}.market{background:#ecfeff;color:#0e7490}.wa-menu{margin-left:auto}.wa{background:var(--ui-success-soft);color:var(--ui-success)}.wa-menu[open]>.wa{filter:saturate(1.2)}.prices{background:var(--ui-warning-soft);color:var(--ui-warning)}.prices-menu[open]>.prices{filter:saturate(1.2)}.action-menu-items{position:absolute;z-index:30;right:0;bottom:calc(100% + 6px);min-width:190px;padding:5px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-raised);box-shadow:var(--ui-shadow-popover)}.products-menu .action-menu-items{right:auto;left:0}.action-menu-items button,.action-menu-items a{display:flex;width:100%;align-items:center;justify-content:space-between;padding:8px 10px;border:0;border-radius:var(--ui-radius-xs);background:transparent;color:var(--ui-text);font:500 .78rem var(--ui-font-sans);text-align:left;text-decoration:none;white-space:nowrap;cursor:pointer}.action-menu-items button:hover,.action-menu-items a:hover{background:var(--ui-surface-muted)}.action-menu-items svg{margin-left:5px}@media(max-width:700px){.inquiry-card-actions{flex-wrap:wrap}.wa-menu{margin-left:0}}
</style>
