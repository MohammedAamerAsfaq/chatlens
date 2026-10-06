<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  loading: Boolean,
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 25 },
  pageSizes: { type: Array, default: () => [10, 25, 50, 100] },
  sortKey: { type: String, default: '' },
  sortDirection: { type: String, default: 'asc' },
  search: { type: String, default: '' },
  searchPlaceholder: { type: String, default: 'Search records...' },
  emptyTitle: { type: String, default: 'No records found' },
  persistKey: { type: String, default: '' },
  exportFilename: { type: String, default: 'records.csv' },
  expandable: Boolean,
  rowClass: { type: Function, default: () => '' },
})

const emit = defineEmits([
  'update:page', 'update:pageSize', 'update:sortKey', 'update:sortDirection',
  'update:search', 'refresh',
])

const internalSearch = ref(props.search)
const expanded = ref(new Set())
const showColumns = ref(false)
const hiddenKeys = ref(new Set())
let searchTimer

const visibleColumns = computed(() => props.columns.filter(column => !hiddenKeys.value.has(column.key)))
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const firstRecord = computed(() => props.total ? ((props.page - 1) * props.pageSize) + 1 : 0)
const lastRecord = computed(() => Math.min(props.page * props.pageSize, props.total))
const pageNumbers = computed(() => {
  const start = Math.max(1, Math.min(props.page - 2, totalPages.value - 4))
  const end = Math.min(totalPages.value, start + 4)
  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
})

watch(() => props.search, value => { internalSearch.value = value })
watch(hiddenKeys, persistColumns, { deep: true })

function storageKey() {
  return props.persistKey ? `chatlens:datatable:${props.persistKey}:hidden` : ''
}

function restoreColumns() {
  if (!storageKey()) return
  try { hiddenKeys.value = new Set(JSON.parse(localStorage.getItem(storageKey()) || '[]')) } catch { hiddenKeys.value = new Set() }
}

function persistColumns() {
  if (storageKey()) localStorage.setItem(storageKey(), JSON.stringify([...hiddenKeys.value]))
}

function toggleColumn(key) {
  const next = new Set(hiddenKeys.value)
  next.has(key) ? next.delete(key) : next.add(key)
  hiddenKeys.value = next
}

function updateSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => emit('update:search', internalSearch.value.trim()), 300)
}

function sort(column) {
  if (!column.sortable) return
  if (props.sortKey === column.key) {
    emit('update:sortDirection', props.sortDirection === 'asc' ? 'desc' : 'asc')
  } else {
    emit('update:sortKey', column.key)
    emit('update:sortDirection', 'asc')
  }
  emit('update:page', 1)
}

function toggleExpanded(row) {
  if (!props.expandable) return
  const key = row[props.rowKey]
  expanded.value = expanded.value.has(key) ? new Set() : new Set([key])
}

function exportPage() {
  const quote = value => `"${String(value ?? '').replaceAll('"', '""')}"`
  const exportColumns = visibleColumns.value.filter(column => column.exportable !== false)
  const lines = [exportColumns.map(column => quote(column.label)).join(',')]
  for (const row of props.rows) {
    lines.push(exportColumns.map(column => quote(column.exportValue ? column.exportValue(row) : row[column.key])).join(','))
  }
  const blob = new Blob([`\ufeff${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = props.exportFilename
  link.click()
  URL.revokeObjectURL(link.href)
}

function closeMenus(event) {
  if (!event.target.closest('.ui-data-table__columns')) showColumns.value = false
}

onMounted(() => { restoreColumns(); document.addEventListener('click', closeMenus) })
onBeforeUnmount(() => { clearTimeout(searchTimer); document.removeEventListener('click', closeMenus) })
</script>

<template>
  <section class="ui-data-table">
    <header class="ui-data-table__toolbar">
      <div class="ui-data-table__filters"><slot name="filters" /></div>
      <div class="ui-data-table__tools">
        <label class="ui-data-table__search"><span aria-hidden="true">&#128269;</span><input v-model="internalSearch" :placeholder="searchPlaceholder" @input="updateSearch"></label>
        <div class="ui-data-table__columns">
          <button type="button" @click.stop="showColumns = !showColumns">Columns</button>
          <div v-if="showColumns" class="ui-data-table__column-menu">
            <label v-for="column in columns" :key="column.key"><input type="checkbox" :checked="!hiddenKeys.has(column.key)" :disabled="!hiddenKeys.has(column.key) && visibleColumns.length === 1" @change="toggleColumn(column.key)"><span>{{ column.label }}</span></label>
          </div>
        </div>
        <button type="button" :disabled="!rows.length" @click="exportPage">Export CSV</button>
        <button type="button" :disabled="loading" aria-label="Refresh records" @click="emit('refresh')">Refresh</button>
      </div>
    </header>

    <div class="ui-data-table__viewport">
      <table>
        <thead><tr><th v-for="column in visibleColumns" :key="column.key" :style="{ width: column.width }" :class="column.headerClass"><button v-if="column.sortable" type="button" @click="sort(column)">{{ column.label }} <span>{{ sortKey === column.key ? (sortDirection === 'asc' ? '&#9650;' : '&#9660;') : '&#8645;' }}</span></button><span v-else>{{ column.label }}</span></th></tr></thead>
        <tbody>
          <tr v-if="loading"><td :colspan="visibleColumns.length" class="ui-data-table__state"><i class="ui-spinner" />Loading records...</td></tr>
          <tr v-else-if="!rows.length"><td :colspan="visibleColumns.length" class="ui-data-table__state">{{ emptyTitle }}</td></tr>
          <template v-for="row in rows" v-else :key="row[rowKey]">
            <tr :class="[rowClass(row), { 'is-expanded': expanded.has(row[rowKey]), 'is-expandable': expandable }]" @click="toggleExpanded(row)"><td v-for="column in visibleColumns" :key="column.key" :class="column.cellClass"><slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">{{ row[column.key] }}</slot></td></tr>
            <tr v-if="expandable && expanded.has(row[rowKey])" class="ui-data-table__detail"><td :colspan="visibleColumns.length"><slot name="expanded" :row="row" /></td></tr>
          </template>
        </tbody>
      </table>
    </div>

    <footer class="ui-data-table__footer">
      <span>Showing {{ firstRecord.toLocaleString() }}-{{ lastRecord.toLocaleString() }} of {{ total.toLocaleString() }}</span>
      <label>Rows <select :value="pageSize" @change="emit('update:pageSize', Number($event.target.value))"><option v-for="size in pageSizes" :key="size" :value="size">{{ size }}</option></select></label>
      <nav aria-label="Table pagination"><button :disabled="page <= 1" @click="emit('update:page', page - 1)">Previous</button><button v-for="number in pageNumbers" :key="number" :class="{ active: number === page }" @click="emit('update:page', number)">{{ number }}</button><button :disabled="page >= totalPages" @click="emit('update:page', page + 1)">Next</button></nav>
    </footer>
  </section>
</template>
