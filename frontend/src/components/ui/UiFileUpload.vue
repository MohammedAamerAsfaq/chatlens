<script setup>
import { ref } from 'vue'

defineProps({ accept: { type: String, default: '' }, disabled: { type: Boolean, default: false }, label: { type: String, default: 'Choose file' }, fileName: { type: String, default: '' } })
const emit = defineEmits(['select', 'clear'])
const input = ref(null)
function selected(event) { const file = event.target.files?.[0]; event.target.value = ''; if (file) emit('select', file) }
</script>

<template><div class="ui-upload"><input ref="input" type="file" :accept="accept" :disabled="disabled" @change="selected" /><button type="button" class="ui-upload__pick" :disabled="disabled" @click="input?.click()">{{ label }}</button><span>{{ fileName || 'No file selected' }}</span><button v-if="fileName" type="button" class="ui-upload__clear" aria-label="Remove selected file" @click="$emit('clear')">×</button></div></template>
