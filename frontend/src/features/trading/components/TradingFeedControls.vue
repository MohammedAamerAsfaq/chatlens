<script setup>
import { computed } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faArrowDownWideShort, faArrowUpShortWide } from '@fortawesome/free-solid-svg-icons'

const props = defineProps({
  contactSearch: { type: String, default: '' },
  selectedContact: { type: [String, Number], default: '' },
  contactOpen: { type: Boolean, default: false },
  contactLoading: { type: Boolean, default: false },
  contactOptions: { type: Array, default: () => [] },
  dateRange: { type: String, required: true },
  dateOptions: { type: Array, default: () => [] },
  sort: { type: String, required: true },
  pageSize: { type: Number, required: true },
  pageSizeOptions: { type: Array, default: () => [] },
})

const emit = defineEmits([
  'update:contactSearch', 'update:dateRange', 'update:sort', 'update:pageSize',
  'open-contact', 'search-contact', 'clear-contact', 'select-contact',
  'contact-scroll', 'change-date', 'change-sort', 'change-page-size',
])

function contactLabel(contact) {
  return contact?.display_name || contact?.push_name || contact?.phone_number || contact?.wa_contact_id || `Contact ${contact?.id || ''}`
}

function updateSearch(event) {
  emit('update:contactSearch', event.target.value)
  emit('search-contact')
}

function updateDate(event) {
  emit('update:dateRange', event.target.value)
  emit('change-date')
}

const newestFirst = computed(() => props.sort !== 'oldest')
const sortLabel = computed(() => newestFirst.value ? 'Newest first' : 'Oldest first')

function toggleSort() {
  emit('update:sort', newestFirst.value ? 'oldest' : 'latest')
  emit('change-sort')
}

function updatePageSize(event) {
  emit('update:pageSize', Number(event.target.value))
  emit('change-page-size')
}
</script>

<template>
  <div class="trading-feed-controls">
    <div class="contact-picker">
      <input :value="contactSearch" class="feed-input" placeholder="Search contact..." @focus="$emit('open-contact')" @input="updateSearch" />
      <button v-if="selectedContact" type="button" class="contact-clear" title="Clear contact filter" @click="$emit('clear-contact')">x</button>
      <div v-if="contactOpen" class="contact-menu" @scroll="$emit('contact-scroll', $event)">
        <button type="button" class="contact-option muted" @mousedown.prevent="$emit('clear-contact')">All contacts</button>
        <button v-for="contact in contactOptions" :key="contact.id" type="button" class="contact-option" @mousedown.prevent="$emit('select-contact', contact)">
          <span class="contact-main"><span>{{ contactLabel(contact) }}</span><span class="account-badge">{{ contact.account_name || `Account ${contact.account_id}` }}</span></span>
          <small>{{ contact.phone_number || contact.wa_contact_id }}</small>
        </button>
        <div v-if="contactLoading" class="contact-loading">Loading...</div>
        <div v-else-if="!contactOptions.length" class="contact-loading">No contacts</div>
      </div>
    </div>
    <select :value="dateRange" class="feed-select" aria-label="Date range" @change="updateDate"><option v-for="option in dateOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select>
    <button type="button" class="sort-button" :title="sortLabel" :aria-label="`Sort inquiries: ${sortLabel}`" @click="toggleSort">
      <FontAwesomeIcon :icon="newestFirst ? faArrowDownWideShort : faArrowUpShortWide" />
    </button>
    <select :value="pageSize" class="feed-select compact" aria-label="Records per page" @change="updatePageSize"><option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option></select>
  </div>
</template>

<style scoped>
.trading-feed-controls{display:flex;align-items:center;gap:6px;margin-left:auto}.feed-select,.feed-input{height:28px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);font:500 .78rem var(--ui-font-sans);padding:2px 8px}.feed-select:focus,.feed-input:focus{border-color:var(--ui-primary);outline:0;box-shadow:var(--ui-focus-ring)}.feed-select.compact{width:62px}.sort-button{display:grid;width:28px;height:28px;place-items:center;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text-muted);cursor:pointer}.sort-button:hover{border-color:var(--ui-primary);color:var(--ui-primary)}.contact-picker{position:relative;width:170px}.feed-input{width:100%;padding-right:22px}.contact-clear{position:absolute;right:5px;top:5px;border:0;background:transparent;color:var(--ui-text-subtle);cursor:pointer;font-size:.74rem;line-height:1}.contact-menu{position:absolute;z-index:30;top:32px;left:0;width:260px;max-height:230px;overflow-y:auto;padding:4px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-sm);background:var(--ui-surface-raised);box-shadow:var(--ui-shadow-popover)}.contact-option{display:flex;width:100%;flex-direction:column;align-items:flex-start;gap:1px;padding:6px 8px;border:0;border-radius:var(--ui-radius-xs);background:transparent;color:var(--ui-text);font:500 .78rem var(--ui-font-sans);text-align:left;cursor:pointer}.contact-option:hover{background:var(--ui-surface-muted)}.contact-option.muted{color:var(--ui-text-muted);font-weight:700}.contact-main{display:flex;width:100%;align-items:center;justify-content:space-between;gap:8px}.account-badge{max-width:98px;overflow:hidden;padding:1px 7px;border-radius:var(--ui-radius-pill);background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.64rem;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.contact-option small{color:var(--ui-text-subtle);font-size:.68rem}.contact-loading{padding:8px;color:var(--ui-text-subtle);font-size:.74rem;text-align:center}@media(max-width:760px){.trading-feed-controls{width:100%;flex-wrap:wrap;margin-left:0}.contact-picker{flex:1;min-width:170px}}
</style>
