<script setup>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faAngleLeft, faAngleRight, faAnglesLeft, faAnglesRight } from '@fortawesome/free-solid-svg-icons'
const props = defineProps({ page: { type: Number, required: true }, pages: { type: Number, required: true } })
const emit = defineEmits(['change'])
function go(page) {
  if (page < 1 || page > props.pages || page === props.page) return
  emit('change', page)
}
</script>

<template>
  <nav class="ui-pagination" aria-label="Pagination">
    <button :disabled="page<=1" title="First page" aria-label="First page" @click="go(1)"><FontAwesomeIcon :icon="faAnglesLeft" /></button>
    <button :disabled="page<=1" title="Previous page" aria-label="Previous page" @click="go(page-1)"><FontAwesomeIcon :icon="faAngleLeft" /></button>
    <span>Page {{ page }} of {{ pages }}</span>
    <button :disabled="page>=pages" title="Next page" aria-label="Next page" @click="go(page+1)"><FontAwesomeIcon :icon="faAngleRight" /></button>
    <button :disabled="page>=pages" title="Last page" aria-label="Last page" @click="go(pages)"><FontAwesomeIcon :icon="faAnglesRight" /></button>
  </nav>
</template>
