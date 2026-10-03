<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineProps({ align: { type: String, default: 'end' } })
const open = ref(false)
const root = ref(null)
function close() { open.value = false }
function onPointerDown(event) { if (!root.value?.contains(event.target)) close() }
onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onPointerDown))
</script>

<template>
  <div ref="root" class="ui-dropdown" @keydown.esc="close">
    <div @click="open=!open"><slot name="trigger" :open="open" /></div>
    <Transition name="ui-popover"><div v-if="open" class="ui-dropdown__menu" :class="`ui-dropdown__menu--${align}`" @click="close"><slot /></div></Transition>
  </div>
</template>
