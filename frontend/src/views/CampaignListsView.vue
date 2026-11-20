<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { campaignListsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiTabs from '@/components/ui/UiTabs.vue'

// Saved, reusable lists for campaigns: contact lists (direct buying and selling),
// group lists (group campaigns) and product lists (any campaign). Each is used on its
// own, from a campaign's "Add from saved list" pickers.
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canManage = computed(() => auth.hasPermission('campaigns.audiences.manage'))

const KINDS = {
  contacts: { noun: 'contact', title: 'Contact lists', subtitle: 'Recipients for direct buying and selling campaigns.', search: 'Search contacts by name or phone...', skipped: 'contact(s) are no longer on your company accounts' },
  groups: { noun: 'group', title: 'Group lists', subtitle: 'Recipients for group buying and selling campaigns.', search: 'Search sendable groups by name...', skipped: 'group(s) are no longer sendable' },
  products: { noun: 'product', title: 'Product lists', subtitle: 'Products for any campaign, direct or group.', search: 'Search products by name, brand, SKU or alias...', skipped: 'product(s) are inactive' },
}
const kind = ref(KINDS[route.query.kind] ? route.query.kind : 'contacts')
const kindInfo = computed(() => KINDS[kind.value])
const lists = ref([])
const loading = ref(true)
const selected = ref(null)
const error = ref('')
const notice = ref('')
const busy = ref('')
const newName = ref('')
const editing = reactive({ active: false, name: '', description: '' })
const search = ref('')
const candidates = reactive({ rows: [], count: 0, page: 1, pageSize: 25, searched: false })
const confirmDelete = ref(false)

const noun = computed(() => kindInfo.value.noun)
const tabs = computed(() => [
  { value: 'contacts', label: 'Contact lists' },
  { value: 'groups', label: 'Group lists' },
  { value: 'products', label: 'Product lists' },
])
const candidatePages = computed(() => Math.max(1, Math.ceil(candidates.count / candidates.pageSize)))
const unusableCount = computed(() => (selected.value?.members || []).filter(row => !row.usable).length)

function message(exc, fallback) {
  const data = exc?.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
async function run(key, action, fallback) {
  busy.value = key; error.value = ''; notice.value = ''
  try { await action() } catch (exc) { error.value = message(exc, fallback) }
  finally { busy.value = '' }
}
function resetCandidates() {
  Object.assign(candidates, { rows: [], count: 0, page: 1, searched: false })
  search.value = ''
}
function storeDetail(data) {
  selected.value = data
  const index = lists.value.findIndex(row => row.id === data.id)
  const summary = { ...data }
  delete summary.members
  if (index === -1) lists.value.push(summary)
  else lists.value[index] = summary
}

async function loadLists() {
  loading.value = true; error.value = ''
  try {
    lists.value = (await campaignListsApi.list({ kind: kind.value })).data
  } catch (exc) {
    error.value = message(exc, 'Unable to load saved lists.')
  } finally {
    loading.value = false
  }
}
function select(item) {
  editing.active = false
  resetCandidates()
  return run(`open-${item.id}`, async () => { selected.value = (await campaignListsApi.get(item.id)).data }, 'Unable to open the list.')
}
function createList() {
  const name = newName.value.trim()
  if (!name) return
  return run('create', async () => {
    const { data } = await campaignListsApi.create({ kind: kind.value, name })
    newName.value = ''
    storeDetail(data)
    resetCandidates()
  }, 'Unable to create the list.')
}
function startEdit() {
  Object.assign(editing, { active: true, name: selected.value.name, description: selected.value.description })
}
function saveEdit() {
  return run('rename', async () => {
    storeDetail((await campaignListsApi.update(selected.value.id, { name: editing.name, description: editing.description })).data)
    editing.active = false
  }, 'Unable to save the list.')
}
function deleteList() {
  const target = selected.value
  return run('delete', async () => {
    await campaignListsApi.remove(target.id)
    lists.value = lists.value.filter(row => row.id !== target.id)
    selected.value = null
    confirmDelete.value = false
    notice.value = `Deleted “${target.name}”.`
  }, 'Unable to delete the list.')
}
function searchCandidates(page = 1) {
  return run('search', async () => {
    const { data } = await campaignListsApi.candidates(selected.value.id, { search: search.value, page })
    Object.assign(candidates, { rows: data.results, count: data.count, page: data.page, pageSize: data.page_size, searched: true })
  }, `Unable to search ${noun.value}s.`)
}
function afterAdd(data) {
  storeDetail(data.list)
  notice.value = `${data.added} added${data.skipped ? `, ${data.skipped} already on the list` : ''}.`
}
function addMember(row) {
  return run(`add-${row.id}`, async () => {
    afterAdd((await campaignListsApi.addMembers(selected.value.id, { ids: [row.id] })).data)
    candidates.rows = candidates.rows.filter(item => item.id !== row.id)
    candidates.count -= 1
  }, `Unable to add the ${noun.value}.`)
}
function addAllMatching() {
  return run('add-all', async () => {
    afterAdd((await campaignListsApi.addMembers(selected.value.id, { all_matching: true, search: search.value })).data)
    Object.assign(candidates, { rows: [], count: 0, page: 1 })
  }, `Unable to add the ${noun.value}s.`)
}
function removeMember(row) {
  return run(`remove-${row.id}`, async () => {
    storeDetail((await campaignListsApi.removeMembers(selected.value.id, [row.id])).data.list)
  }, `Unable to remove the ${noun.value}.`)
}

watch(kind, value => {
  selected.value = null
  resetCandidates()
  router.replace({ query: { ...route.query, kind: value } })
  loadLists()
})
onMounted(loadLists)
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader
      eyebrow="Campaigns"
      title="Saved lists"
      description="Reusable contact, group and product lists. Each is added to a campaign on its own, from that campaign's “Add from saved list” pickers."
    />
    <UiTabs v-model="kind" :tabs="tabs" />
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-else-if="notice" tone="success">{{ notice }}</UiNotice>

    <div class="lists-layout">
      <UiCard :title="kindInfo.title" :subtitle="kindInfo.subtitle">
        <form v-if="canManage" class="lists-create" @submit.prevent="createList">
          <UiInput v-model="newName" :placeholder="`New ${noun} list name`" maxlength="120" />
          <UiButton type="submit" variant="primary" :disabled="busy === 'create' || !newName.trim()">{{ busy === 'create' ? 'Creating...' : 'Create' }}</UiButton>
        </form>
        <UiEmptyState v-if="loading" title="Loading lists..." busy />
        <UiEmptyState v-else-if="!lists.length" :title="`No ${noun} lists yet`" :description="canManage ? 'Create the first one above.' : 'An administrator can create lists here.'" />
        <ul v-else class="lists-index">
          <li v-for="item in lists" :key="item.id">
            <button type="button" :class="{ active: selected?.id === item.id }" @click="select(item)">
              <strong>{{ item.name }}</strong>
              <span>{{ item.member_count }} {{ noun }}{{ item.member_count === 1 ? '' : 's' }}</span>
            </button>
          </li>
        </ul>
      </UiCard>

      <UiCard v-if="selected" :title="selected.name" :subtitle="selected.description || `Created by ${selected.created_by || 'unknown'}`">
        <template v-if="canManage" #actions>
          <div class="lists-actions">
            <UiButton size="small" variant="outline" @click="startEdit">Rename</UiButton>
            <UiButton size="small" variant="danger" @click="confirmDelete = true">Delete</UiButton>
          </div>
        </template>

        <form v-if="editing.active" class="lists-edit" @submit.prevent="saveEdit">
          <UiInput v-model="editing.name" placeholder="List name" maxlength="120" />
          <UiInput v-model="editing.description" placeholder="Description (optional)" />
          <div class="lists-actions">
            <UiButton type="submit" size="small" variant="primary" :disabled="busy === 'rename' || !editing.name.trim()">Save</UiButton>
            <UiButton size="small" variant="outline" @click="editing.active = false">Cancel</UiButton>
          </div>
        </form>

        <section v-if="canManage" class="lists-add">
          <h3>Add {{ noun }}s</h3>
          <form class="lists-search" @submit.prevent="searchCandidates(1)">
            <UiInput v-model="search" :placeholder="kindInfo.search" />
            <UiButton type="submit" :disabled="busy === 'search'">{{ busy === 'search' ? 'Searching...' : 'Search' }}</UiButton>
          </form>
          <template v-if="candidates.searched">
            <div class="lists-search-summary">
              <span>{{ candidates.count }} not yet on the list</span>
              <UiButton size="small" variant="primary" :disabled="!candidates.count || busy === 'add-all'" @click="addAllMatching">
                {{ busy === 'add-all' ? 'Adding...' : `Add all ${candidates.count}` }}
              </UiButton>
            </div>
            <ul class="lists-rows">
              <li v-for="row in candidates.rows" :key="row.id">
                <div><strong>{{ row.name }}</strong><small>{{ row.detail }} · {{ row.account_name }}</small></div>
                <UiButton size="small" variant="outline" :disabled="Boolean(busy)" :aria-label="`Add ${row.name}`" @click="addMember(row)">Add</UiButton>
              </li>
            </ul>
            <UiPagination v-if="candidatePages > 1" :page="candidates.page" :pages="candidatePages" @change="searchCandidates" />
          </template>
        </section>

        <section class="lists-members">
          <h3>On this list <UiBadge>{{ selected.member_count }}</UiBadge></h3>
          <UiNotice v-if="unusableCount" tone="warning">
            {{ unusableCount }} {{ kindInfo.skipped }} and will be skipped when this list is added to a campaign.
          </UiNotice>
          <p v-if="selected.hidden_member_count" class="lists-hint">{{ selected.hidden_member_count }} more on WhatsApp accounts you can't see.</p>
          <UiEmptyState v-if="!selected.members.length" :title="`No ${noun}s on this list`" :description="canManage ? 'Search above to add some.' : ''" />
          <ul v-else class="lists-rows">
            <li v-for="row in selected.members" :key="row.id" :class="{ unusable: !row.usable }">
              <div>
                <strong>{{ row.name }} <UiBadge v-if="!row.usable" tone="warning">Skipped</UiBadge></strong>
                <small>{{ row.detail }} · {{ row.account_name }}</small>
              </div>
              <UiButton v-if="canManage" size="small" variant="outline" :disabled="Boolean(busy)" :aria-label="`Remove ${row.name}`" @click="removeMember(row)">Remove</UiButton>
            </li>
          </ul>
        </section>
      </UiCard>
      <UiCard v-else>
        <UiEmptyState title="Choose a list" :description="`Pick a ${noun} list to see and change who is on it.`" />
      </UiCard>
    </div>

    <UiConfirmModal
      :open="confirmDelete" title="Delete list" danger confirm-label="Delete" :busy="busy === 'delete'"
      :message="`Delete “${selected?.name}”? Campaigns that already used it keep their recipients.`"
      @confirm="deleteList" @cancel="confirmDelete = false"
    />
  </UiPage>
</template>

<style scoped>
.lists-layout{display:grid;grid-template-columns:minmax(240px,320px) minmax(0,1fr);gap:16px;align-items:start;margin-top:14px}
.lists-create,.lists-search{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;margin-bottom:12px}
.lists-edit{display:grid;gap:8px;margin-bottom:14px}
.lists-actions{display:flex;gap:6px}
.lists-index{display:grid;gap:6px;margin:0;padding:0;list-style:none}
.lists-index button{display:flex;width:100%;justify-content:space-between;gap:8px;padding:9px 11px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-muted);color:var(--ui-text);font:inherit;text-align:left;cursor:pointer}
.lists-index button.active,.lists-index button:hover{border-color:var(--ui-primary);color:var(--ui-primary)}
.lists-index span{color:var(--ui-text-muted);font-size:.76rem;white-space:nowrap}
.lists-add,.lists-members{margin-top:12px}
.lists-add h3,.lists-members h3{display:flex;align-items:center;gap:6px;margin:0 0 8px;font-size:.82rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.lists-search-summary{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;color:var(--ui-text-muted);font-size:.78rem}
.lists-rows{display:grid;gap:6px;margin:0 0 10px;padding:0;list-style:none}
.lists-rows li{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm)}
.lists-rows li.unusable{background:var(--ui-warning-soft,#fff7e6)}
.lists-rows div{min-width:0}
.lists-rows strong{display:flex;align-items:center;gap:6px;font-size:.82rem}
.lists-rows small{color:var(--ui-text-muted);font-size:.72rem}
.lists-hint{margin:0 0 8px;color:var(--ui-text-muted);font-size:.76rem}
@media(max-width:860px){.lists-layout{grid-template-columns:1fr}}
</style>
