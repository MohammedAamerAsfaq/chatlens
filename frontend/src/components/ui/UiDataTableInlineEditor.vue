<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { default: null },
  options: { type: Array, default: () => [] },
  multiple: Boolean,
  disabled: Boolean,
  saving: Boolean,
  emptyLabel: { type: String, default: 'None' },
})
const emit = defineEmits(['save'])
const root = ref(null)
const editing = ref(false)
const draft = ref(props.multiple ? [] : props.modelValue)

const selectedOptions = computed(() => {
  const selected = props.multiple ? (props.modelValue || []) : [props.modelValue]
  return props.options.filter(option => selected.some(value => String(value) === String(option.value)))
})
const displayLabel = computed(() => selectedOptions.value.map(option => option.label).join(', ') || props.emptyLabel)

watch(() => props.modelValue, resetDraft, { deep: true })

function resetDraft() {
  draft.value = props.multiple ? [...(props.modelValue || [])] : props.modelValue
}
function begin() {
  if (props.disabled || props.saving) return
  resetDraft()
  editing.value = true
}
function cancel() {
  resetDraft()
  editing.value = false
}
function saveSingle(event) {
  const option = props.options.find(item => String(item.value) === event.target.value)
  editing.value = false
  emit('save', option ? option.value : event.target.value)
}
function toggle(value) {
  const current = new Set((draft.value || []).map(item => String(item)))
  current.has(String(value)) ? current.delete(String(value)) : current.add(String(value))
  draft.value = props.options.filter(option => current.has(String(option.value))).map(option => option.value)
}
function saveMultiple() {
  editing.value = false
  emit('save', [...draft.value])
}
function closeOutside(event) {
  if (editing.value && !root.value?.contains(event.target)) cancel()
}
function onKeydown(event) {
  if (event.key === 'Escape') cancel()
}

onMounted(() => {
  document.addEventListener('click', closeOutside)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closeOutside)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div ref="root" class="ui-inline-editor" :class="{ 'is-editing': editing, 'is-saving': saving }" @click.stop>
    <button v-if="!editing" type="button" class="ui-inline-editor__value" :disabled="disabled || saving" @click="begin">
      <slot :selected="selectedOptions" :label="displayLabel">{{ displayLabel }}</slot>
      <span class="ui-inline-editor__hint">{{ saving ? 'Saving...' : 'Edit' }}</span>
    </button>
    <select v-else-if="!multiple" class="ui-inline-editor__select" :value="draft ?? ''" autofocus @change="saveSingle" @blur="cancel">
      <option v-for="option in options" :key="option.value ?? 'empty'" :value="option.value">{{ option.label }}</option>
    </select>
    <div v-else class="ui-inline-editor__menu">
      <label v-for="option in options" :key="option.value">
        <input type="checkbox" :checked="draft.some(value => String(value) === String(option.value))" @change="toggle(option.value)">
        <span>{{ option.label }}</span>
      </label>
      <div class="ui-inline-editor__actions">
        <button type="button" @click="cancel">Cancel</button>
        <button type="button" class="primary" @click="saveMultiple">Save</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ui-inline-editor{position:relative;min-width:110px}.ui-inline-editor__value{display:flex;width:100%;min-height:32px;align-items:center;justify-content:space-between;gap:8px;padding:4px 7px;border:1px solid transparent;border-radius:var(--ui-radius-xs);background:transparent;color:var(--ui-text);font:inherit;text-align:left;cursor:pointer}.ui-inline-editor__value:hover:not(:disabled),.ui-inline-editor__value:focus-visible{border-color:var(--ui-primary);background:var(--ui-primary-soft);outline:0}.ui-inline-editor__value:disabled{cursor:default}.ui-inline-editor__hint{color:var(--ui-text-subtle);font-size:.62rem;font-weight:700;opacity:0;text-transform:uppercase}.ui-inline-editor__value:hover .ui-inline-editor__hint,.ui-inline-editor__value:focus-visible .ui-inline-editor__hint,.is-saving .ui-inline-editor__hint{opacity:1}.ui-inline-editor__select{width:100%;min-height:34px;padding:5px 28px 5px 8px;border:1px solid var(--ui-primary);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);font:inherit;outline:0}.ui-inline-editor__menu{position:absolute;z-index:30;top:calc(100% + 4px);left:0;width:220px;max-height:260px;overflow:auto;padding:7px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-raised);box-shadow:var(--ui-shadow-popover)}.ui-inline-editor__menu label{display:flex;align-items:center;gap:8px;padding:7px;border-radius:var(--ui-radius-xs);cursor:pointer}.ui-inline-editor__menu label:hover{background:var(--ui-surface-muted)}.ui-inline-editor__actions{position:sticky;bottom:-7px;display:flex;justify-content:flex-end;gap:6px;margin:6px -7px -7px;padding:7px;border-top:1px solid var(--ui-border);background:var(--ui-surface-raised)}.ui-inline-editor__actions button{padding:5px 9px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);font:700 .7rem var(--ui-font-sans);cursor:pointer}.ui-inline-editor__actions .primary{border-color:var(--ui-primary);background:var(--ui-primary);color:var(--ui-on-primary)}
</style>
