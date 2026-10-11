<script setup>
import { computed, ref, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFileUpload from '@/components/ui/UiFileUpload.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

const props = defineProps({ open: Boolean, busy: Boolean, rows: { type: Array, default: () => [] }, error: { type: String, default: '' } })
const emit = defineEmits(['close', 'preview', 'import'])
const file = ref(null)
const invalidCount = computed(() => props.rows.filter(row => !row.valid).length)
const duplicateCount = computed(() => props.rows.filter(row => row.duplicate_property_id).length)
const importCount = computed(() => props.rows.length - duplicateCount.value)

watch(() => props.open, open => { if (!open) file.value = null })

function preview() { if (file.value) emit('preview', file.value) }
function downloadTemplate() {
  const header = 'reference_code,title,property_type,description,bedrooms,bathrooms,built_up_area,plot_area,area_unit,furnishing,completion_status,developer,project_name,completion_year,availability_status,country,state_region,city,community,project_building,street,unit_number,postal_code,listing_type,asking_price,currency,payment_frequency,available_from,status,is_verified'
  const example = 'SV-001,Marina two-bedroom apartment,apartment,,2,2,1200,,sqft,furnished,ready,,Marina Heights,,available,United Arab Emirates,Dubai,Dubai,Dubai Marina,Marina Heights,,,,sale,2200000,AED,not_applicable,,draft,true'
  const blob = new Blob([`${header}\r\n${example}`], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'real-estate-import-template.csv'; link.click(); URL.revokeObjectURL(link.href)
}
</script>

<template>
  <UiModal :open="open" title="Import properties" subtitle="Preview validation and duplicates before any records are written." size="xlarge" tall @close="emit('close')">
    <div class="import-actions">
      <UiFileUpload accept=".csv,text/csv" :file-name="file?.name || ''" @select="file = $event" @clear="file = null" />
      <UiButton :disabled="busy || !file" @click="preview">{{ busy ? 'Checking...' : 'Validate CSV' }}</UiButton>
      <UiButton @click="downloadTemplate">Download template</UiButton>
    </div>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="rows.length && !invalidCount" tone="success">{{ importCount }} records are ready. {{ duplicateCount }} exact duplicates will be skipped.</UiNotice>
    <div v-if="rows.length" class="preview-table"><table><thead><tr><th>Row</th><th>Reference</th><th>Property</th><th>Type</th><th>Listing</th><th>Result</th></tr></thead><tbody>
      <tr v-for="row in rows" :key="row.row_number" :class="{ invalid: !row.valid }"><td>{{ row.row_number }}</td><td>{{ row.reference_code || '-' }}</td><td>{{ row.title }}</td><td>{{ row.property_type }}</td><td>{{ row.listing_type || '-' }} {{ row.asking_price || '' }}</td><td><span v-if="!row.valid">{{ Object.values(row.errors).join(' ') }}</span><span v-else-if="row.duplicate_property_id">Duplicate of #{{ row.duplicate_property_id }} {{ row.duplicate_title }}</span><span v-else>Ready</span></td></tr>
    </tbody></table></div>
    <template #footer><UiButton @click="emit('close')">Cancel</UiButton><UiButton variant="primary" :disabled="busy || !rows.length || Boolean(invalidCount) || !importCount" @click="emit('import', rows)">{{ busy ? 'Importing...' : `Import ${importCount} properties` }}</UiButton></template>
  </UiModal>
</template>

<style scoped>
.import-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:16px}.preview-table{overflow:auto;max-height:52vh;border:1px solid var(--ui-border);border-radius:10px;margin-top:16px}.preview-table table{width:100%;border-collapse:collapse}.preview-table th,.preview-table td{padding:10px;border-bottom:1px solid var(--ui-border);text-align:left;vertical-align:top}.preview-table th{position:sticky;top:0;background:var(--ui-surface-muted)}.preview-table .invalid{background:#fff2f2}.preview-table td:last-child{min-width:240px}
</style>
