<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faGear } from '@fortawesome/free-solid-svg-icons'

defineProps({
  accounts: { type: Array, default: () => [] },
  selectedAccount: { type: [String, Number], default: '' },
  closeStaleHours: { type: Number, default: 1 },
  closeStaleRunning: { type: Boolean, default: false },
  slideDirection: { type: String, default: 'left' },
})
const emit = defineEmits([
  'update:selectedAccount', 'update:closeStaleHours', 'update:slideDirection',
  'change-account', 'change-animation', 'close-stale',
])
const open = ref(false)
const root = ref(null)

function updateDirection(event) {
  emit('update:slideDirection', event.target.value)
  emit('change-animation')
}

function updateAccount(event) {
  emit('update:selectedAccount', event.target.value)
  emit('change-account')
}

function updateHours(event) {
  emit('update:closeStaleHours', Number(event.target.value))
}

function closeOutside(event) {
  if (open.value && !root.value?.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener('pointerdown', closeOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeOutside))
</script>

<template>
  <div ref="root" class="toolbar-settings">
    <button
      type="button"
      class="icon-button"
      title="Trading Dashboard settings"
      aria-label="Trading Dashboard settings"
      :aria-expanded="open"
      @click="open = !open"
    >
      <FontAwesomeIcon :icon="faGear" />
    </button>
    <div v-if="open" class="settings-popover">
      <strong>Trading Dashboard Settings</strong>
      <label class="setting-field">
        <span>Account</span>
        <select :value="selectedAccount" @change="updateAccount">
          <option value="">All accounts</option>
          <option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.display_name }}</option>
        </select>
      </label>
      <label class="setting-field">
        <span>Card status animation</span>
        <select :value="slideDirection" @change="updateDirection">
          <option value="left">Slide left</option>
          <option value="right">Slide right</option>
          <option value="none">Off</option>
        </select>
      </label>
      <div class="setting-field">
        <span>Close stale inquiries</span>
        <div class="stale-controls">
          <input :value="closeStaleHours" type="number" min="1" step="1" aria-label="Stale inquiry age in hours" @input="updateHours" />
          <button type="button" :disabled="closeStaleRunning" @click="$emit('close-stale')">
            {{ closeStaleRunning ? 'Closing...' : `Close older than ${closeStaleHours || 1}h` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar-settings{position:relative}.icon-button{display:grid;width:30px;height:30px;place-items:center;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text-muted);cursor:pointer}.icon-button:hover{border-color:var(--ui-primary);color:var(--ui-primary)}.settings-popover{position:absolute;z-index:40;top:36px;right:0;width:275px;padding:14px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-raised);box-shadow:var(--ui-shadow-popover)}.settings-popover strong{display:block;margin-bottom:12px;font-size:.82rem}.setting-field{display:grid;gap:6px;margin-top:11px;color:var(--ui-text-muted);font-size:.72rem;font-weight:700}.setting-field select,.setting-field input{height:32px;padding:0 8px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text)}.stale-controls{display:flex;gap:6px}.stale-controls input{width:52px}.stale-controls button{flex:1;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-primary);color:var(--ui-primary-contrast);font-weight:700;cursor:pointer}.stale-controls button:disabled{cursor:wait;opacity:.6}
</style>
