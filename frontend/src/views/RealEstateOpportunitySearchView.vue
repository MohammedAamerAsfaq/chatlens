<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { formatDate, moneyRange, opportunityLanes, opportunityParty, statusFilters } from '@/features/realEstate/boardOptions'

const router = useRouter()
const activeActivity = ref('buying')
const query = ref('')
const submittedQuery = ref('')
const status = ref('')
const relevance = ref('possible')
const groupDuplicates = ref(true)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref('')
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const tabs = opportunityLanes.map(lane => ({ value: lane.key, label: lane.label }))
const pageSizes = [10, 20, 50].map(value => ({ value, label: `${value} results` }))
const relevanceOptions = [
  { value: 'strong', label: 'Strong matches only' },
  { value: 'possible', label: 'Strong + possible' },
  { value: 'all', label: 'All semantic results' },
]

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await realEstateApi.searchOpportunities({
      activity_type: activeActivity.value,
      q: submittedQuery.value || undefined,
      status: status.value || undefined,
      relevance: relevance.value,
      group_duplicates: groupDuplicates.value,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = data.results || data
    total.value = data.count ?? rows.value.length
  } catch (exc) {
    error.value = apiError(exc, 'Unable to search Real Estate opportunities.')
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function submitSearch() {
  submittedQuery.value = query.value.trim()
  page.value = 1
  load()
}

function itemDescription(item) {
  return [item.property_type_name || item.property_type_label, item.location_raw].filter(Boolean).join(' - ')
}

function itemRange(item) {
  return moneyRange(item.currency, item.amount_min, item.amount_max)
}

function openOpportunity(id) {
  router.push({ name: 'real-estate-opportunity-detail', params: { id } })
}

function relevanceTone(value) {
  return value === 'strong' ? 'success' : value === 'possible' ? 'warning' : 'neutral'
}

function changePage(value) {
  page.value = value
  load()
}

watch(activeActivity, () => { page.value = 1; load() })
watch(status, () => { page.value = 1; load() })
watch(relevance, () => { page.value = 1; load() })
watch(groupDuplicates, () => { page.value = 1; load() })
watch(pageSize, () => { page.value = 1; load() })
onMounted(load)
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Real Estate Intelligence" title="Opportunity Search" description="Search embedded buyer, seller, tenant, and landlord opportunities by meaning." />
    <UiCard class="opportunity-search">
      <UiTabs v-model="activeActivity" :tabs="tabs" />
      <form class="opportunity-search__controls" @submit.prevent="submitSearch">
        <UiInput v-model="query" placeholder="Describe a property, location, budget, or requirement...">
          <template #prefix><i class="fa-solid fa-magnifying-glass"></i></template>
        </UiInput>
        <UiSelect v-model="status" :options="statusFilters" />
        <UiSelect v-model="relevance" :options="relevanceOptions" />
        <UiSelect v-model="pageSize" :options="pageSizes" />
        <UiCheckbox v-model="groupDuplicates" label="Group similar" />
        <UiButton variant="primary" type="submit" :disabled="loading">
          <i class="fa-solid fa-wand-magic-sparkles"></i> {{ loading ? 'Searching...' : 'Search' }}
        </UiButton>
      </form>
      <p class="opportunity-search__hint">Search combines meaning with property type, bedrooms, price, and location. Relevance tiers control recall; grouping only combines matching results on screen.</p>
    </UiCard>

    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <div class="opportunity-search__summary">
      <strong>{{ total.toLocaleString() }} opportunities</strong>
      <span v-if="submittedQuery">ranked for "{{ submittedQuery }}"</span>
    </div>

    <section v-if="rows.length" class="opportunity-search__results">
      <article v-for="row in rows" :key="row.id" class="opportunity-search__result" role="link" tabindex="0" @click="openOpportunity(row.id)" @keydown.enter="openOpportunity(row.id)">
        <header>
          <div><h2>{{ opportunityParty(row) }}</h2><p>#{{ row.id }} - {{ formatDate(row.first_seen_at) }}</p></div>
          <div class="opportunity-search__badges">
            <UiBadge>{{ row.status }}</UiBadge>
            <UiBadge v-if="row.search_score != null" :tone="relevanceTone(row.search_relevance)">{{ Math.round(row.search_score * 100) }}% {{ row.search_relevance }}</UiBadge>
            <UiBadge v-if="row.duplicate_count > 1" tone="neutral">{{ row.duplicate_count }} similar</UiBadge>
          </div>
        </header>
        <p class="opportunity-search__message">{{ row.summary || row.original_message }}</p>
        <p v-if="row.search_reasons?.length" class="opportunity-search__reasons">Matched on: {{ row.search_reasons.join(', ') }}</p>
        <div class="opportunity-search__items">
          <div v-for="item in row.items" :key="item.id" class="opportunity-search__item">
            <strong>{{ item.title || `Property ${item.sequence}` }}</strong>
            <span>{{ itemDescription(item) || 'Extracted property details' }}</span>
            <span v-if="itemRange(item)">{{ itemRange(item) }}</span>
          </div>
          <span v-if="!row.items?.length" class="opportunity-search__empty">No extracted property items.</span>
        </div>
      </article>
    </section>
    <UiNotice v-else-if="!loading && !error" tone="neutral">No opportunities match this search.</UiNotice>
    <UiPagination :page="page" :pages="pages" @change="changePage" />
  </UiPage>
</template>

<style scoped>
.opportunity-search { margin-bottom: 1rem; }
.opportunity-search__controls { display:grid; grid-template-columns:minmax(18rem,1fr) 12rem 13rem 10rem auto auto; gap:.75rem; align-items:center; margin-top:1rem; }
.opportunity-search__hint,.opportunity-search__summary span,.opportunity-search__result header p,.opportunity-search__item span,.opportunity-search__empty { color:var(--ui-text-muted); }
.opportunity-search__hint { margin:.65rem 0 0; font-size:.86rem; }
.opportunity-search__summary { display:flex; gap:.5rem; margin:.75rem 0; }
.opportunity-search__results { display:grid; gap:.8rem; }
.opportunity-search__result { background:var(--ui-surface); border:1px solid var(--ui-border); border-left:4px solid var(--ui-primary); border-radius:var(--ui-radius); padding:1rem; cursor:pointer; }
.opportunity-search__result:hover { box-shadow:var(--ui-shadow); transform:translateY(-1px); }
.opportunity-search__result header { display:flex; justify-content:space-between; gap:1rem; }
.opportunity-search__result h2,.opportunity-search__result header p { margin:0; }
.opportunity-search__badges { display:flex; gap:.4rem; align-items:flex-start; }
.opportunity-search__message { margin:.8rem 0; }
.opportunity-search__reasons { margin:-.35rem 0 .8rem; color:var(--ui-text-muted); font-size:.82rem; }
.opportunity-search__items { display:grid; grid-template-columns:repeat(auto-fit,minmax(16rem,1fr)); gap:.5rem; }
.opportunity-search__item { display:flex; flex-direction:column; gap:.15rem; padding:.65rem; background:var(--ui-surface-muted); border-radius:calc(var(--ui-radius) - 2px); }
@media (max-width:900px) { .opportunity-search__controls { grid-template-columns:1fr; } .opportunity-search__result header { flex-direction:column; } }
</style>
