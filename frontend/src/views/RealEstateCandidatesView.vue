<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import CandidateReviewModal from '@/features/realEstate/components/CandidateReviewModal.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { title } from '@/features/realEstate/options'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const rows = ref([]), listings = ref([]), total = ref(0), page = ref(1), pageSize = ref(25)
const propertyTypes = ref([])
const loading = ref(false), error = ref(''), search = ref('')
const filters = reactive({ review_status: 'pending', activity_type: '' })
const review = reactive({ open: false, candidate: null, busy: false })
const canReview = computed(() => auth.hasPermission('real_estate.opportunities.update'))
const reviewStatuses = ['pending', 'promoted', 'merged', 'rejected'].map(value => ({ value, label: title(value) }))
const activities = [{ value: '', label: 'All offer activities' }, { value: 'selling', label: 'Selling' }, { value: 'leasing_offer', label: 'Leasing Offer' }]
const columns = [
  { key: 'title', label: 'Candidate', width: '21rem' }, { key: 'activity_type', label: 'Activity' },
  { key: 'property_type', label: 'Type' }, { key: 'location_raw', label: 'Location' },
  { key: 'asking_price', label: 'Asking price' }, { key: 'review_status', label: 'Review' },
  { key: 'updated_at', label: 'Updated' }, { key: 'actions', label: '', exportable: false, width: '9rem' },
]

async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await realEstateApi.candidates({ page: page.value, page_size: pageSize.value, search: search.value, ...filters })
    rows.value = data.results; total.value = data.count
  } catch (exc) { error.value = apiError(exc, 'Unable to load candidates.') }
  finally { loading.value = false }
}
async function loadListings() {
  try { listings.value = (await realEstateApi.listings({ page_size: 100 })).data.results } catch (exc) { error.value = apiError(exc, 'Unable to load listings.') }
}
async function loadPropertyTypes() {
  try {
    const { data } = await realEstateApi.propertyTypes({ page_size: 100 })
    propertyTypes.value = data.results.map(record => ({ value: record.code, label: record.name }))
  } catch (exc) { error.value = apiError(exc, 'Unable to load property types.') }
}
function openReview(candidate) { review.candidate = candidate; review.open = true }
async function execute(action) {
  review.busy = true; error.value = ''
  try { await action(); review.open = false; await Promise.all([load(), loadListings()]) }
  catch (exc) { error.value = apiError(exc, 'Unable to review the candidate.') }
  finally { review.busy = false }
}
function promote(payload) { return execute(() => realEstateApi.promoteCandidate(review.candidate.id, payload)) }
function merge(listingId) { return execute(() => realEstateApi.mergeCandidate(review.candidate.id, listingId)) }
function reject() { return execute(() => realEstateApi.rejectCandidate(review.candidate.id)) }
function money(row) { return row.asking_price == null ? '-' : `${row.currency} ${Number(row.asking_price).toLocaleString()}` }
function resetAndLoad() { if (page.value !== 1) page.value = 1; else load() }
watch(() => [filters.review_status, filters.activity_type], resetAndLoad)
watch(search, resetAndLoad)
watch([page, pageSize], load)
onMounted(() => Promise.all([load(), loadListings(), loadPropertyTypes()]))
</script>

<template><UiPage width="wide"><UiPageHeader eyebrow="Trust Boundary" title="Candidate Review" description="AI-extracted offers remain untrusted until an authorized user promotes, merges, or rejects them." /><UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
  <UiDataTable :columns="columns" :rows="rows" :loading="loading" :total="total" :page="page" :page-size="pageSize" :search="search" persist-key="real-estate-candidates" search-placeholder="Search candidates..." empty-title="No candidates match these filters." @update:page="page = $event" @update:page-size="pageSize = $event; page = 1" @update:search="search = $event" @refresh="load">
    <template #filters><UiSelect v-model="filters.review_status" :options="reviewStatuses" /><UiSelect v-model="filters.activity_type" :options="activities" /></template>
    <template #cell-title="{ row }"><strong>{{ row.title || `Candidate #${row.id}` }}</strong><small class="subline">Opportunity #{{ row.opportunity }}</small></template><template #cell-activity_type="{ value }">{{ title(value) }}</template><template #cell-property_type="{ value }">{{ title(value || 'other') }}</template><template #cell-location_raw="{ value }">{{ value || '-' }}</template><template #cell-asking_price="{ row }">{{ money(row) }}</template><template #cell-review_status="{ value }"><UiBadge :tone="value === 'pending' ? 'warning' : value === 'rejected' ? 'danger' : 'success'">{{ title(value) }}</UiBadge></template><template #cell-updated_at="{ value }">{{ new Date(value).toLocaleString() }}</template><template #cell-actions="{ row }"><UiButton v-if="canReview && row.review_status === 'pending'" size="small" variant="primary" @click.stop="openReview(row)">Review</UiButton></template>
  </UiDataTable><CandidateReviewModal :open="review.open" :candidate="review.candidate" :listings="listings" :property-types="propertyTypes" :busy="review.busy" @close="review.open = false" @promote="promote" @merge="merge" @reject="reject" />
</UiPage></template>

<style scoped>.subline{display:block;color:var(--ui-text-subtle);margin-top:3px}</style>
