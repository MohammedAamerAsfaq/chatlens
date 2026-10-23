<script setup>
const props = defineProps({ page: { type: Number, required: true }, pages: { type: Number, required: true } })
const emit = defineEmits(['change'])
function go(page) {
  if (page < 1 || page > props.pages || page === props.page) return
  emit('change', page)
}
</script>

<template>
  <nav class="ui-pagination" aria-label="Pagination">
    <button :disabled="page<=1" title="First page" aria-label="First page" @click="go(1)"><i class="fa-solid fa-angles-left"></i></button>
    <button :disabled="page<=1" title="Previous page" aria-label="Previous page" @click="go(page-1)"><i class="fa-solid fa-angle-left"></i></button>
    <span>Page {{ page }} of {{ pages }}</span>
    <button :disabled="page>=pages" title="Next page" aria-label="Next page" @click="go(page+1)"><i class="fa-solid fa-angle-right"></i></button>
    <button :disabled="page>=pages" title="Last page" aria-label="Last page" @click="go(pages)"><i class="fa-solid fa-angles-right"></i></button>
  </nav>
</template>
