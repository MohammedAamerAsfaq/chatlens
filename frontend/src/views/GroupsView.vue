<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { groupsApi, accountsApi } from '@/api/index.js'

// ── State ──────────────────────────────────────────────────────────────────────
const accounts      = ref([])
const selectedAccId = ref(null)
const groups        = ref([])
const stats         = ref({ total: 0, communities: 0, groups: 0 })
const loading       = ref(false)
const syncing       = ref(false)
const syncMsg       = ref('')
const search        = ref('')
const typeFilter    = ref('all')   // 'all' | 'community' | 'group'
const page          = ref(1)
const totalCount    = ref(0)
const pageSize      = 25

// Detail panel
const selectedGroup = ref(null)
const detailLoading = ref(false)

// ── Derived ────────────────────────────────────────────────────────────────────
const totalPages = computed(() => Math.ceil(totalCount.value / pageSize))

const communityGroups = computed(() =>
  groups.value.filter(g => g.is_community)
)
const regularGroups = computed(() =>
  groups.value.filter(g => !g.is_community)
)

// ── API calls ──────────────────────────────────────────────────────────────────
async function fetchAccounts() {
  const res = await accountsApi.list()
  accounts.value = res.data.results || res.data
  if (accounts.value.length && !selectedAccId.value) {
    selectedAccId.value = accounts.value[0].id
  }
}

async function fetchStats() {
  const params = {}
  if (selectedAccId.value) params.account = selectedAccId.value
  const res = await groupsApi.stats(params)
  stats.value = res.data
}

async function fetchGroups() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (selectedAccId.value) params.account = selectedAccId.value
    if (search.value.trim())  params.search = search.value.trim()
    if (typeFilter.value !== 'all') params.type = typeFilter.value
    const res = await groupsApi.list(params)
    const data = res.data
    groups.value    = data.results || data
    totalCount.value = data.count   || groups.value.length
  } finally {
    loading.value = false
  }
}

async function fetchGroupDetail(id) {
  detailLoading.value = true
  selectedGroup.value = null
  try {
    const res = await groupsApi.get(id)
    selectedGroup.value = res.data
  } finally {
    detailLoading.value = false
  }
}

// ── Event handlers ─────────────────────────────────────────────────────────────
function selectAccount(id) {
  selectedAccId.value = id
  page.value = 1
  selectedGroup.value = null
}

function applySearch() {
  page.value = 1
  fetchGroups()
}

function setTypeFilter(t) {
  typeFilter.value = t
  page.value = 1
  fetchGroups()
}

function openGroup(g) {
  fetchGroupDetail(g.id)
}

function closeDetail() {
  selectedGroup.value = null
}

function prevPage() {
  if (page.value > 1) { page.value--; fetchGroups() }
}
function nextPage() {
  if (page.value < totalPages.value) { page.value++; fetchGroups() }
}

async function syncGroups() {
  if (!selectedAccId.value || syncing.value) return
  syncing.value = true
  syncMsg.value = ''
  try {
    const res = await groupsApi.syncGroups(selectedAccId.value)
    syncMsg.value = `Synced ${res.data.synced} groups`
    await Promise.all([fetchStats(), fetchGroups()])
  } catch (err) {
    const msg = err.response?.data?.error || err.message
    syncMsg.value = `Error: ${msg}`
  } finally {
    syncing.value = false
    setTimeout(() => { syncMsg.value = '' }, 5000)
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function roleColor(role) {
  if (role === 'superadmin') return 'text-yellow-400'
  if (role === 'admin')      return 'text-blue-400'
  return 'text-gray-400'
}

function roleLabel(role) {
  if (role === 'superadmin') return 'Owner'
  if (role === 'admin')      return 'Admin'
  return 'Member'
}

function formatJid(jid) {
  if (!jid) return ''
  const local = jid.split('@')[0]
  return local.length > 15 ? local.slice(0, 13) + '…' : local
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await fetchAccounts()
  await Promise.all([fetchStats(), fetchGroups()])
})

watch(selectedAccId, () => {
  page.value = 1
  selectedGroup.value = null
  Promise.all([fetchStats(), fetchGroups()])
})
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden bg-gray-50">

    <!-- Header bar -->
    <div class="bg-white border-b border-gray-200 px-6 py-3 shrink-0">
      <div class="flex items-center gap-4 flex-wrap">
        <h1 class="text-lg font-semibold text-gray-800">Groups &amp; Communities</h1>

        <!-- Account tabs -->
        <div class="flex gap-1">
          <button
            v-for="acc in accounts"
            :key="acc.id"
            @click="selectAccount(acc.id)"
            :class="[
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              selectedAccId === acc.id
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
            ]"
          >
            {{ acc.display_name || acc.phone_number || `#${acc.id}` }}
          </button>
        </div>

        <!-- Stats chips + sync -->
        <div class="flex gap-2 ml-auto items-center text-xs">
          <span class="px-2 py-0.5 bg-gray-100 rounded-full text-gray-600">
            {{ stats.total }} total
          </span>
          <span class="px-2 py-0.5 bg-purple-100 rounded-full text-purple-700">
            {{ stats.communities }} communities
          </span>
          <span class="px-2 py-0.5 bg-blue-100 rounded-full text-blue-700">
            {{ stats.groups }} groups
          </span>
          <span v-if="syncMsg" :class="[
            'px-2 py-0.5 rounded-full font-medium',
            syncMsg.startsWith('Error') ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-700',
          ]">{{ syncMsg }}</span>
          <button
            @click="syncGroups"
            :disabled="syncing || !selectedAccId"
            class="flex items-center gap-1 px-3 py-1 rounded-lg bg-indigo-600 text-white font-medium text-xs hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            <svg v-if="syncing" class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            <svg v-else class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ syncing ? 'Syncing…' : 'Sync Groups' }}
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex gap-3 mt-2 items-center flex-wrap">
        <input
          v-model="search"
          @keydown.enter="applySearch"
          placeholder="Search groups..."
          class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-green-400"
        />
        <button @click="applySearch" class="text-sm px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
          Search
        </button>

        <div class="flex gap-1 ml-2">
          <button
            v-for="t in [{v:'all',l:'All'},{v:'community',l:'Communities'},{v:'group',l:'Groups'}]"
            :key="t.v"
            @click="setTypeFilter(t.v)"
            :class="[
              'px-3 py-1 rounded-full text-xs font-medium transition-colors',
              typeFilter === t.v
                ? 'bg-gray-800 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
            ]"
          >
            {{ t.l }}
          </button>
        </div>
      </div>
    </div>

    <!-- Main content -->
    <div class="flex-1 flex overflow-hidden min-h-0">

      <!-- Group list -->
      <div :class="['flex flex-col border-r border-gray-200 bg-white overflow-hidden', selectedGroup ? 'w-1/2' : 'flex-1']">

        <!-- Loading -->
        <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Loading…
        </div>

        <!-- Empty -->
        <div v-else-if="!groups.length" class="flex-1 flex flex-col items-center justify-center gap-2 text-gray-400 px-8 text-center">
          <svg class="w-10 h-10 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0" />
          </svg>
          <p class="text-sm font-medium">No groups found</p>
          <p class="text-xs">Click <strong>Sync Groups</strong> to fetch metadata for all groups the connected account participates in.</p>
        </div>

        <!-- Table -->
        <div v-else class="flex-1 overflow-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
              <tr>
                <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide w-8"></th>
                <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Name</th>
                <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Community</th>
                <th class="text-right px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Members</th>
                <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Updated</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr
                v-for="g in groups"
                :key="g.id"
                @click="openGroup(g)"
                :class="[
                  'cursor-pointer transition-colors hover:bg-gray-50',
                  selectedGroup?.id === g.id ? 'bg-green-50' : '',
                ]"
              >
                <!-- Type icon -->
                <td class="px-4 py-3 text-center">
                  <span v-if="g.is_community" class="text-purple-500 text-base" title="Community">⬡</span>
                  <span v-else class="text-blue-400 text-base" title="Group">⊞</span>
                </td>

                <!-- Name + JID -->
                <td class="px-4 py-3">
                  <div class="font-medium text-gray-800 truncate max-w-[220px]">
                    {{ g.name || g.wa_group_id }}
                  </div>
                  <div class="text-[10px] font-mono text-gray-400 mt-0.5 truncate">
                    {{ g.wa_group_id }}
                  </div>
                </td>

                <!-- Community parent -->
                <td class="px-4 py-3">
                  <span v-if="g.is_community" class="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded-full font-medium">
                    Community ({{ g.sub_group_count }} groups)
                  </span>
                  <span v-else-if="g.community_name" class="text-[11px] text-purple-500 truncate max-w-[140px] block">
                    {{ g.community_name }}
                  </span>
                  <span v-else class="text-[11px] text-gray-300">—</span>
                </td>

                <!-- Participant count -->
                <td class="px-4 py-3 text-right tabular-nums text-gray-600 font-mono text-xs">
                  {{ g.participant_count }}
                </td>

                <!-- Updated -->
                <td class="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                  {{ new Date(g.updated_at).toLocaleDateString() }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="border-t border-gray-200 px-4 py-2 flex items-center justify-between shrink-0 bg-white">
          <span class="text-xs text-gray-500">{{ totalCount }} groups · page {{ page }}/{{ totalPages }}</span>
          <div class="flex gap-1">
            <button @click="prevPage" :disabled="page === 1"
              class="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50">
              ‹ Prev
            </button>
            <button @click="nextPage" :disabled="page === totalPages"
              class="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50">
              Next ›
            </button>
          </div>
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="selectedGroup || detailLoading" class="w-1/2 flex flex-col bg-white overflow-hidden">

        <!-- Loading -->
        <div v-if="detailLoading" class="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Loading…
        </div>

        <template v-else-if="selectedGroup">
          <!-- Panel header -->
          <div class="border-b border-gray-200 px-5 py-3 shrink-0 flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span v-if="selectedGroup.is_community" class="text-purple-500 text-lg">⬡</span>
                <span v-else class="text-blue-400 text-lg">⊞</span>
                <h2 class="text-base font-semibold text-gray-800 truncate">
                  {{ selectedGroup.name || selectedGroup.wa_group_id }}
                </h2>
              </div>
              <p class="text-[11px] font-mono text-gray-400 mt-0.5 break-all">{{ selectedGroup.wa_group_id }}</p>
              <div v-if="selectedGroup.community_name" class="mt-1 text-xs text-purple-500">
                Part of community: {{ selectedGroup.community_name }}
              </div>
              <div v-if="selectedGroup.is_community" class="mt-1 text-xs text-purple-600 font-medium">
                Community umbrella · {{ selectedGroup.sub_group_count }} sub-groups
              </div>
            </div>
            <button @click="closeDetail" class="text-gray-400 hover:text-gray-600 shrink-0 mt-0.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Meta -->
          <div class="px-5 py-3 border-b border-gray-100 shrink-0 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            <div v-if="selectedGroup.description" class="col-span-2">
              <span class="text-xs text-gray-400 uppercase font-medium block mb-0.5">Description</span>
              <p class="text-gray-700 text-xs leading-relaxed">{{ selectedGroup.description }}</p>
            </div>
            <div>
              <span class="text-xs text-gray-400 uppercase font-medium block">Owner</span>
              <span class="text-xs font-mono text-gray-600">{{ formatJid(selectedGroup.owner_jid) || '—' }}</span>
            </div>
            <div>
              <span class="text-xs text-gray-400 uppercase font-medium block">Members</span>
              <span class="text-xs text-gray-800 font-semibold">{{ selectedGroup.participant_count }}</span>
            </div>
          </div>

          <!-- Participants list -->
          <div class="flex-1 overflow-auto">
            <div v-if="!selectedGroup.participants?.length" class="p-5 text-sm text-gray-400 text-center">
              No participant data available yet.
            </div>
            <table v-else class="w-full text-sm">
              <thead class="bg-gray-50 border-b border-gray-200 sticky top-0">
                <tr>
                  <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Participant</th>
                  <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 uppercase">Role</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="p in selectedGroup.participants" :key="p.id">
                  <td class="px-4 py-2.5">
                    <div v-if="p.display_name !== p.wa_jid" class="text-gray-800 font-medium text-xs">
                      {{ p.display_name }}
                    </div>
                    <div class="text-[10px] font-mono text-gray-400">
                      {{ formatJid(p.wa_jid) }}@{{ p.wa_jid.includes('@') ? p.wa_jid.split('@')[1] : '' }}
                    </div>
                  </td>
                  <td class="px-4 py-2.5">
                    <span :class="['text-xs font-medium', roleColor(p.role)]">{{ roleLabel(p.role) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
