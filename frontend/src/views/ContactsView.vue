<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { contactsApi, accountsApi } from '@/api'

const router = useRouter()

const contacts    = ref([])
const accounts    = ref([])
const stats       = ref({ total: 0, phone: 0, lid: 0, group: 0 })
const loading     = ref(false)
const savingId    = ref(null)

// Filters
const filterAccount = ref('all')
const filterType    = ref('all')
const searchQuery   = ref('')

// Pagination
const page            = ref(1)
const pageSize        = ref(50)
const totalCount      = ref(0)
const pageSizeOptions = [25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

// Inline edit state: { [contactId]: string }
const editValues = ref({})
const editingId  = ref(null)

const TYPE_LABEL = { phone: 'Phone', lid: 'LID', group: 'Group', unknown: 'Unknown' }
const TYPE_STYLE = {
  phone:   'bg-green-100 text-green-700',
  lid:     'bg-purple-100 text-purple-700',
  group:   'bg-orange-100 text-orange-700',
  unknown: 'bg-gray-100 text-gray-500',
}

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') p.account = filterAccount.value
  if (filterType.value    !== 'all') p.type    = filterType.value
  if (searchQuery.value.trim())      p.search  = searchQuery.value.trim()
  return p
}

async function fetchContacts(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await contactsApi.list(buildParams())
    contacts.value   = data.results
    totalCount.value = data.count
  } catch {}
  finally { loading.value = false }
}

async function fetchStats() {
  try {
    const params = filterAccount.value !== 'all' ? { account: filterAccount.value } : {}
    const { data } = await contactsApi.stats(params)
    stats.value = data
  } catch {}
}

async function fetchAccounts() {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data.results ?? data
  } catch {}
}

watch([filterAccount, filterType, pageSize], () => {
  page.value = 1
  fetchContacts()
  fetchStats()
})
watch(page, () => fetchContacts())

let searchTimer = null
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; fetchContacts() }, 300)
})

onMounted(() => {
  fetchAccounts()
  fetchContacts(true)
  fetchStats()
})

// ── Inline edit ──────────────────────────────────────────────────────────────

function startEdit(contact) {
  editingId.value = contact.id
  editValues.value[contact.id] = contact.display_name
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(contact) {
  const newName = (editValues.value[contact.id] ?? '').trim()
  savingId.value = contact.id
  try {
    const { data } = await contactsApi.update(contact.id, { display_name: newName })
    const idx = contacts.value.findIndex(c => c.id === contact.id)
    if (idx !== -1) contacts.value[idx] = data
    editingId.value = null
  } catch {}
  finally { savingId.value = null }
}

function handleEditKeydown(e, contact) {
  if (e.key === 'Enter')  saveEdit(contact)
  if (e.key === 'Escape') cancelEdit()
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function initials(contact) {
  const name = contact.display_name || contact.push_name
  if (!name) return (contact.phone_number || '?')[0]
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
}

function avatarColor(contact) {
  const colors = [
    'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
    'bg-red-500', 'bg-teal-500', 'bg-pink-500', 'bg-indigo-500',
  ]
  const id = contact.id || 0
  return colors[id % colors.length]
}

function displayLabel(contact) {
  return contact.display_name || contact.push_name || (contact.phone_number ? `+${contact.phone_number}` : contact.wa_contact_id)
}

function openChat(contact) {
  if (!contact.chat_db_id) return
  router.push({ name: 'conversations', query: { chat_id: contact.chat_db_id } })
}
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">Contacts</h1>
      <p class="text-sm text-gray-500 mt-1">Manage WhatsApp contacts and their display names</p>
    </div>

    <!-- Stats -->
    <div class="flex items-center gap-6 mb-6 bg-white rounded-xl border border-gray-200 px-6 py-4 shadow-sm">
      <div>
        <p class="text-xs text-gray-400 uppercase tracking-wide">Total</p>
        <p class="text-xl font-bold text-gray-900">{{ stats.total.toLocaleString() }}</p>
      </div>
      <div class="w-px h-8 bg-gray-100"></div>
      <div>
        <p class="text-xs text-green-500 uppercase tracking-wide">Phone</p>
        <p class="text-xl font-bold text-gray-900">{{ stats.phone.toLocaleString() }}</p>
      </div>
      <div class="w-px h-8 bg-gray-100"></div>
      <div>
        <p class="text-xs text-purple-500 uppercase tracking-wide">LID <span class="normal-case text-gray-400 font-normal">(privacy-mode)</span></p>
        <p class="text-xl font-bold text-gray-900">{{ stats.lid.toLocaleString() }}</p>
      </div>
      <div class="w-px h-8 bg-gray-100"></div>
      <div>
        <p class="text-xs text-orange-500 uppercase tracking-wide">Groups</p>
        <p class="text-xl font-bold text-gray-900">{{ stats.group.toLocaleString() }}</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">

      <select
        v-model="filterAccount"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[160px]"
      >
        <option value="all">All accounts</option>
        <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
          {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
        </option>
      </select>

      <select
        v-model="filterType"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="all">All types</option>
        <option value="phone">Phone</option>
        <option value="lid">LID</option>
        <option value="group">Group</option>
      </select>

      <!-- Search -->
      <div class="relative flex-1 min-w-[220px]">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search name, phone, JID…"
          class="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
        />
      </div>

      <span class="text-sm text-gray-400">{{ totalCount.toLocaleString() }} contacts</span>

      <!-- Page size -->
      <div class="flex items-center gap-2 text-sm text-gray-500">
        <span>Rows:</span>
        <div class="flex border border-gray-200 rounded-lg overflow-hidden">
          <button
            v-for="n in pageSizeOptions"
            :key="n"
            @click="pageSize = n"
            :class="['px-2.5 py-1 text-xs transition-colors', pageSize === n ? 'bg-green-600 text-white' : 'hover:bg-gray-50 text-gray-600']"
          >{{ n }}</button>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading…</div>

      <div v-else-if="contacts.length === 0" class="text-center text-gray-400 py-12 text-sm">
        No contacts found
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-12"></th>
            <th class="text-left px-4 py-3">Display Name</th>
            <th class="text-left px-4 py-3 w-44">WhatsApp Name</th>
            <th class="text-left px-4 py-3 w-36">Phone</th>
            <th class="text-left px-4 py-3 w-24">Type</th>
            <th class="text-left px-4 py-3 w-20">Msgs</th>
            <th class="text-left px-4 py-3 w-28">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <tr
            v-for="contact in contacts"
            :key="contact.id"
            class="hover:bg-gray-50 transition-colors"
          >
            <!-- Avatar -->
            <td class="px-4 py-3">
              <div :class="['w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0', avatarColor(contact)]">
                {{ initials(contact) }}
              </div>
            </td>

            <!-- Display name (inline editable) -->
            <td class="px-4 py-3">
              <div v-if="editingId === contact.id" class="flex items-center gap-1.5">
                <input
                  v-model="editValues[contact.id]"
                  @keydown="handleEditKeydown($event, contact)"
                  autofocus
                  class="flex-1 text-sm border border-green-400 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-green-500 min-w-0"
                />
                <button
                  @click="saveEdit(contact)"
                  :disabled="savingId === contact.id"
                  class="p-1 rounded text-green-600 hover:bg-green-50 disabled:opacity-40 transition-colors"
                  title="Save"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
                  </svg>
                </button>
                <button
                  @click="cancelEdit"
                  class="p-1 rounded text-gray-400 hover:bg-gray-100 transition-colors"
                  title="Cancel"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                </button>
              </div>
              <div
                v-else
                class="group flex items-center gap-1.5 cursor-pointer"
                @click="startEdit(contact)"
                title="Click to edit display name"
              >
                <span :class="['text-sm font-medium truncate max-w-[200px]', contact.display_name ? 'text-gray-900' : 'text-gray-400 italic']">
                  {{ contact.display_name || 'Set display name…' }}
                </span>
                <svg class="w-3.5 h-3.5 text-gray-300 group-hover:text-green-500 shrink-0 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
                </svg>
              </div>
            </td>

            <!-- Push name (from WhatsApp) -->
            <td class="px-4 py-3">
              <span class="text-sm text-gray-600 truncate block max-w-[160px]">
                {{ contact.push_name || '—' }}
              </span>
            </td>

            <!-- Phone + LID alias -->
            <td class="px-4 py-3">
              <span class="text-xs font-mono text-gray-700">
                {{ contact.phone_number ? `+${contact.phone_number}` : '—' }}
              </span>
              <span
                v-if="contact.lid_jid"
                class="block text-[10px] font-mono text-purple-400 mt-0.5"
                :title="`LID alias: ${contact.lid_jid}`"
              >
                {{ contact.lid_jid.split('@')[0] }}@lid
              </span>
            </td>

            <!-- Type -->
            <td class="px-4 py-3">
              <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', TYPE_STYLE[contact.contact_type] || TYPE_STYLE.unknown]">
                {{ TYPE_LABEL[contact.contact_type] || contact.contact_type }}
              </span>
              <span v-if="contact.is_business" class="ml-1 text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">Biz</span>
            </td>

            <!-- Message count -->
            <td class="px-4 py-3">
              <span class="text-xs text-gray-500">{{ (contact.message_count || 0).toLocaleString() }}</span>
            </td>

            <!-- Actions -->
            <td class="px-4 py-3">
              <button
                v-if="contact.chat_db_id"
                @click="openChat(contact)"
                class="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-green-200 text-green-700 hover:bg-green-50 transition-colors"
                title="Open conversation"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                Chat
              </button>
              <span v-else class="text-xs text-gray-300">No chat</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="totalCount > 0" class="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50 text-sm text-gray-500">
        <span>Showing {{ pageStart.toLocaleString() }}–{{ pageEnd.toLocaleString() }} of {{ totalCount.toLocaleString() }}</span>
        <div class="flex items-center gap-1">
          <button
            @click="page--"
            :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >← Prev</button>
          <span class="px-3 py-1.5 text-xs">Page {{ page }} of {{ totalPages }}</span>
          <button
            @click="page++"
            :disabled="page >= totalPages"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >Next →</button>
        </div>
      </div>
    </div>

  </div>
  </div>
</template>
