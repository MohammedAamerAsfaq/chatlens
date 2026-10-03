<script setup>
const props = defineProps({ page: { type: Number, required: true }, pages: { type: Number, required: true } })
const emit = defineEmits(['change'])
</script>

<template><nav class="ui-pagination" aria-label="Pagination"><button :disabled="props.page<=1" @click="emit('change',props.page-1)">Previous</button><span>Page {{props.page}} of {{props.pages}}</span><button :disabled="props.page>=props.pages" @click="emit('change',props.page+1)">Next</button></nav></template>
