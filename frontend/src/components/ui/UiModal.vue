<script setup>
import { onBeforeUnmount, useId, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  size: { type: String, default: 'medium' },
  closeable: { type: Boolean, default: true },
})
const emit = defineEmits(['close'])
const titleId = useId()
function close() { if (props.closeable) emit('close') }
function onKeydown(event) { if (event.key === 'Escape') close() }
watch(() => props.open, open => open ? document.addEventListener('keydown', onKeydown) : document.removeEventListener('keydown', onKeydown), { immediate: true })
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body"><Transition name="ui-modal">
    <div v-if="open" class="ui-modal-backdrop" @mousedown.self="close">
      <section class="ui-modal" :class="`ui-modal--${size}`" role="dialog" aria-modal="true" :aria-labelledby="titleId">
        <header><h2 :id="titleId">{{ title }}</h2><button v-if="closeable" type="button" aria-label="Close" @click="close">×</button></header>
        <div class="ui-modal__body"><slot /></div>
        <footer v-if="$slots.footer"><slot name="footer" /></footer>
      </section>
    </div>
  </Transition></Teleport>
</template>
