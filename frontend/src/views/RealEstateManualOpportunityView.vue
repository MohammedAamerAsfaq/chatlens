<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDatePicker from '@/components/ui/UiDatePicker.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ManualInquiryItem from '@/features/realEstate/components/ManualInquiryItem.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { activityOptions, emptyInquiryItem, scopeOptions, statusOptions } from '@/features/realEstate/manualInquiryOptions'

const router = useRouter()
const media = ref([]), propertyTypeRecords = ref([]), loading = ref(true), saving = ref(false)
const error = ref(''), newMediumName = ref(''), addingMedium = ref(false)
const form = reactive({
  activity_type: 'buying', inquiry_medium: '', source_party_name: '',
  source_contact_detail: '', source_reference: '', received_at: localNow(),
  market_scope: 'local', status: 'new', summary: '', original_message: '',
  items: [emptyInquiryItem()],
})
const mediaOptions = computed(() => media.value.map(row => ({ value: row.id, label: row.name })))
const propertyTypeOptions = computed(() => propertyTypeRecords.value.map(row => ({ value: row.code, label: row.name })))
const demand = computed(() => ['buying', 'leasing_inquiry'].includes(form.activity_type))

function localNow() {
  const date = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
  return date.toISOString().slice(0, 16)
}
function rows(response) { return response.data.results || response.data }
function addItem() { form.items.push(emptyInquiryItem()) }
function removeItem(index) { form.items.splice(index, 1) }
function updateItem(index, item) { form.items[index] = item }
function clean(item) {
  return Object.fromEntries(Object.entries(item).map(([key, value]) => [
    key, ['bedrooms_min', 'bedrooms_max', 'bathrooms_min', 'bathrooms_max', 'area_min', 'area_max', 'amount_min', 'amount_max', 'available_from']
      .includes(key) && value === '' ? null : value,
  ]))
}

async function loadOptions() {
  loading.value = true; error.value = ''
  try {
    const [mediaResponse, typesResponse] = await Promise.all([
      realEstateApi.inquiryMedia({ page_size: 100 }),
      realEstateApi.propertyTypes({ include_inactive: false, page_size: 100 }),
    ])
    media.value = rows(mediaResponse); propertyTypeRecords.value = rows(typesResponse)
    if (!form.inquiry_medium && media.value.length) form.inquiry_medium = media.value[0].id
  } catch (exc) { error.value = apiError(exc, 'Unable to load inquiry form options.') }
  finally { loading.value = false }
}

async function addMedium() {
  const name = newMediumName.value.trim()
  if (!name) return
  addingMedium.value = true; error.value = ''
  try {
    const { data } = await realEstateApi.createInquiryMedium({ name, is_active: true, sort_order: media.value.length * 10 })
    media.value.push(data); form.inquiry_medium = data.id; newMediumName.value = ''
  } catch (exc) { error.value = apiError(exc, 'Unable to add the inquiry medium.') }
  finally { addingMedium.value = false }
}

async function submit() {
  saving.value = true; error.value = ''
  try {
    const payload = {
      ...form,
      received_at: form.received_at || null,
      items: form.items.map(clean),
    }
    const { data } = await realEstateApi.createManualOpportunity(payload)
    await router.push({ name: 'real-estate-board', query: { lane: data.activity_type } })
  } catch (exc) { error.value = apiError(exc, 'Unable to create the inquiry.') }
  finally { saving.value = false }
}
onMounted(loadOptions)
</script>

<template>
  <UiPage>
    <UiPageHeader eyebrow="Real estate opportunities" title="Create inquiry" description="Record a structured inquiry from any channel and place it directly in the correct opportunity lane.">
      <template #actions><UiButton @click="router.push({ name: 'real-estate-board' })">Cancel</UiButton><UiButton variant="primary" type="submit" form="manual-inquiry-form" :disabled="saving || loading">{{ saving ? 'Saving...' : 'Create inquiry' }}</UiButton></template>
    </UiPageHeader>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <form id="manual-inquiry-form" class="inquiry-form" @submit.prevent="submit">
      <UiCard title="Inquiry source" subtitle="Who sent it, when it arrived, and through which communication medium.">
        <div class="form-grid">
          <UiRadioGroup v-model="form.activity_type" label="Inquiry type" :options="activityOptions" required class="wide" />
          <UiFormField label="Medium"><UiSelect v-model="form.inquiry_medium" :options="mediaOptions" placeholder="Select inquiry medium" searchable required /></UiFormField>
          <UiFormField label="Add another medium" hint="Company-specific media can be added as new channels are introduced."><div class="inline-add"><UiInput v-model="newMediumName" placeholder="e.g. Property portal" /><UiButton :disabled="addingMedium || !newMediumName.trim()" @click="addMedium">Add</UiButton></div></UiFormField>
          <UiFormField label="Party name"><UiInput v-model="form.source_party_name" required /></UiFormField>
          <UiFormField label="Contact detail" hint="Phone number, email address, username, or other identifier."><UiInput v-model="form.source_contact_detail" /></UiFormField>
          <UiFormField label="Source reference" hint="Email subject, call reference, web lead ID, or meeting reference."><UiInput v-model="form.source_reference" /></UiFormField>
          <UiFormField label="Received at"><UiDatePicker v-model="form.received_at" mode="datetime" /></UiFormField>
          <UiRadioGroup v-model="form.market_scope" label="Market scope" :options="scopeOptions" />
          <UiRadioGroup v-model="form.status" label="Workflow status" :options="statusOptions" />
          <UiFormField label="Summary" class="wide"><UiInput v-model="form.summary" multiline :rows="3" required /></UiFormField>
          <UiFormField label="Original inquiry" hint="The exact message or the operator's call/meeting notes." class="wide"><UiInput v-model="form.original_message" multiline :rows="5" /></UiFormField>
        </div>
      </UiCard>
      <UiCard title="Property details" subtitle="These are the same structured fields produced by AI extraction. Add multiple properties when one inquiry covers several units.">
        <div class="items">
          <ManualInquiryItem v-for="(item, index) in form.items" :key="index" :model-value="item" :index="index" :property-types="propertyTypeOptions" :property-type-records="propertyTypeRecords" :demand="demand" :removable="form.items.length > 1" @update:model-value="updateItem(index, $event)" @remove="removeItem(index)" />
          <UiButton @click="addItem"><i class="fa-solid fa-plus"></i> Add another property</UiButton>
        </div>
      </UiCard>
      <div class="footer-actions"><UiButton @click="router.push({ name: 'real-estate-board' })">Cancel</UiButton><UiButton variant="primary" type="submit" :disabled="saving || loading">{{ saving ? 'Saving...' : 'Create inquiry' }}</UiButton></div>
    </form>
  </UiPage>
</template>

<style scoped>
.inquiry-form,.items{display:grid;gap:20px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.wide{grid-column:1/-1}.inline-add{display:grid;grid-template-columns:1fr auto;gap:8px}.footer-actions{display:flex;justify-content:flex-end;gap:10px;padding-bottom:24px}@media(max-width:760px){.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
