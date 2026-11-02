<script setup>
import { ref } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faXmark } from '@fortawesome/free-solid-svg-icons'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Type a value and press Enter' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const draft = ref('')

function normalized(value) {
  return String(value || '').trim().toLocaleLowerCase()
}
function addValues(value) {
  const next = [...props.modelValue]
  const known = new Set(next.map(normalized))
  String(value || '').split(/[\n,]+/).forEach(part => {
    const tag = part.trim()
    const key = normalized(tag)
    if (tag && !known.has(key)) {
      next.push(tag)
      known.add(key)
    }
  })
  emit('update:modelValue', next)
  draft.value = ''
}
function onInput(event) {
  draft.value = event.target.value
  if (draft.value.includes(',')) addValues(draft.value)
}
function onKeydown(event) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault()
    addValues(draft.value)
  } else if (event.key === 'Backspace' && !draft.value && props.modelValue.length) {
    emit('update:modelValue', props.modelValue.slice(0, -1))
  }
}
function onPaste(event) {
  const value = event.clipboardData?.getData('text') || ''
  if (!/[\n,]/.test(value)) return
  event.preventDefault()
  addValues(value)
}
function remove(index) {
  emit('update:modelValue', props.modelValue.filter((_tag, position) => position !== index))
}
</script>

<template>
  <div class="ui-tag-input" :class="{ 'is-disabled': disabled }" @click="$refs.input?.focus()">
    <span v-for="(tag, index) in modelValue" :key="`${tag}-${index}`" class="ui-tag-input__tag">
      {{ tag }}
      <button v-if="!disabled" type="button" :title="`Remove ${tag}`" :aria-label="`Remove ${tag}`" @click.stop="remove(index)">
        <FontAwesomeIcon :icon="faXmark" />
      </button>
    </span>
    <input
      ref="input"
      :value="draft"
      :placeholder="modelValue.length ? '' : placeholder"
      :disabled="disabled"
      @input="onInput"
      @keydown="onKeydown"
      @paste="onPaste"
      @blur="addValues(draft)"
    />
  </div>
</template>

<style scoped>
.ui-tag-input{display:flex;min-height:44px;align-items:center;align-content:center;flex-wrap:wrap;gap:7px;padding:6px 9px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface);cursor:text;transition:border-color .15s ease,box-shadow .15s ease}.ui-tag-input:focus-within{border-color:var(--ui-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--ui-primary) 14%,transparent)}.ui-tag-input.is-disabled{background:var(--ui-surface-muted);cursor:not-allowed;opacity:.7}.ui-tag-input__tag{display:inline-flex;align-items:center;gap:5px;max-width:100%;padding:4px 8px;border-radius:999px;background:color-mix(in srgb,var(--ui-primary) 12%,var(--ui-surface));color:var(--ui-primary);font-size:.84rem;font-weight:700}.ui-tag-input__tag button{display:grid;width:18px;height:18px;place-items:center;padding:0;border:0;border-radius:50%;background:transparent;color:inherit;cursor:pointer}.ui-tag-input__tag button:hover{background:color-mix(in srgb,var(--ui-primary) 18%,transparent)}.ui-tag-input input{min-width:180px;flex:1;padding:5px 2px;border:0;outline:0;background:transparent;color:var(--ui-text);font:inherit}.ui-tag-input input::placeholder{color:var(--ui-text-subtle)}
</style>
