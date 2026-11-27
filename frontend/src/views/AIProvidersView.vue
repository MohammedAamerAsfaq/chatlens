<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { aiProvidersApi, kiwiRoutersApi } from '@/api/index.js'
import ProviderCard from '@/components/ProviderCard.vue'

const router = useRouter()

// ── State ────────────────────────────────────────────────────────────────────

const providers = ref([])
const kiwiRouters = ref([])
const agentTarget = ref({ mode: 'direct', kiwi_router_id: null, kiwi_router_name: '' })
const selectingRouter = ref(null)
const loading   = ref(false)
const error     = ref('')

const testing    = ref({})         // { [id]: 'idle' | 'running' | { ok, ... } }
const deleting   = ref({})

// ── Derived ──────────────────────────────────────────────────────────────────

const embeddingProviders = computed(() => providers.value.filter(p => p.capability === 'embedding'))
const chatProviders      = computed(() => providers.value.filter(p => p.capability === 'chat'))
const agentProviders     = computed(() => providers.value.filter(p => p.capability === 'agent'))

// ── Data ─────────────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  error.value   = ''
  try {
    const [pRes, rRes, targetRes] = await Promise.all([
      aiProvidersApi.list(),
      kiwiRoutersApi.list(),
      aiProvidersApi.agentTarget(),
    ])
    providers.value = pRes.data
    kiwiRouters.value = rRes.data.filter(router => router.capability === 'agent')
    agentTarget.value = targetRes.data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

// Adding and editing happen on their own page.
function openCreate() {
  router.push({ name: 'ai-provider-new' })
}

function openEdit(p) {
  router.push({ name: 'ai-provider-edit', params: { id: p.id } })
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function toggleActive(p) {
  try {
    if (p.is_active) {
      await aiProvidersApi.deactivate(p.id)
    } else {
      await aiProvidersApi.activate(p.id)
    }
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function testProvider(p) {
  testing.value = { ...testing.value, [p.id]: 'running' }
  try {
    const res = await aiProvidersApi.test(p.id)
    testing.value = { ...testing.value, [p.id]: res.data }
  } catch (e) {
    testing.value = { ...testing.value, [p.id]: { ok: false, error: e.message } }
  }
}

async function deleteProvider(p) {
  if (!confirm(`Delete "${p.display_name}"?`)) return
  deleting.value = { ...deleting.value, [p.id]: true }
  try {
    await aiProvidersApi.delete(p.id)
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    deleting.value = { ...deleting.value, [p.id]: false }
  }
}

async function selectRouter(router) {
  selectingRouter.value = router.id
  try {
    const { data } = await aiProvidersApi.setAgentTarget({ kiwi_router_id: router.id })
    agentTarget.value = data
  } catch (e) {
    error.value = e.response?.data?.error || e.message || 'Unable to select KiwiRouter.'
  } finally {
    selectingRouter.value = null
  }
}

async function selectDirectAgent() {
  selectingRouter.value = 'direct'
  try {
    const { data } = await aiProvidersApi.setAgentTarget({ kiwi_router_id: null })
    agentTarget.value = data
  } catch (e) {
    error.value = e.response?.data?.error || e.message || 'Unable to select the direct agent.'
  } finally {
    selectingRouter.value = null
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function testResult(id) {
  return testing.value[id]
}

function capabilityBadge(cap) {
  return cap === 'embedding'
    ? 'bg-blue-100 text-blue-700'
    : 'bg-purple-100 text-purple-700'
}
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="shrink-0 px-6 py-4 bg-white border-b flex items-center justify-between">
      <div>
        <h1 class="text-lg font-semibold text-gray-900">AI Providers</h1>
        <p class="text-sm text-gray-500 mt-0.5">Configure embedding and chat model providers</p>
      </div>
      <button
        @click="openCreate"
        class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
      >
        + Add Provider
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto p-6 space-y-8">
      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
        {{ error }}
      </div>

      <div v-if="loading && !providers.length" class="text-gray-400 text-sm">Loading…</div>

      <!-- Embeddings section -->
      <section>
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Embeddings</h2>
        <div v-if="!embeddingProviders.length" class="text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg px-4 py-8 text-center">
          No embedding providers configured yet
        </div>
        <div class="space-y-3">
          <ProviderCard
            v-for="p in embeddingProviders" :key="p.id"
            :provider="p"
            :test-result="testResult(p.id)"
            :deleting="!!deleting[p.id]"
            @edit="openEdit(p)"
            @toggle-active="toggleActive(p)"
            @test="testProvider(p)"
            @delete="deleteProvider(p)"
          />
        </div>
      </section>

      <!-- Chat section -->
      <section>
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Chat / Completion</h2>
        <div v-if="!chatProviders.length" class="text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg px-4 py-8 text-center">
          No chat providers configured yet
        </div>
        <div class="space-y-3">
          <ProviderCard
            v-for="p in chatProviders" :key="p.id"
            :provider="p"
            :test-result="testResult(p.id)"
            :deleting="!!deleting[p.id]"
            @edit="openEdit(p)"
            @toggle-active="toggleActive(p)"
            @test="testProvider(p)"
            @delete="deleteProvider(p)"
          />
        </div>
      </section>

      <!-- General AI Agent section -->
      <section>
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">General AI Agent</h2>
        <p class="text-xs text-gray-400 mb-3">Direct provider fallback for background tasks. Select a KiwiRouter below when a router-aware workflow should distribute requests across multiple agents.</p>
        <div v-if="!agentProviders.length" class="text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg px-4 py-8 text-center">
          No agent providers configured yet
        </div>
        <div class="space-y-3">
          <ProviderCard
            v-for="p in agentProviders" :key="p.id"
            :provider="p"
            :test-result="testResult(p.id)"
            :deleting="!!deleting[p.id]"
            @edit="openEdit(p)"
            @toggle-active="toggleActive(p)"
            @test="testProvider(p)"
            @delete="deleteProvider(p)"
          />
        </div>
      </section>

      <!-- Kiwi Router section -->
      <section>
        <div class="flex items-center justify-between gap-4 mb-1">
          <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">Kiwi Router</h2>
          <RouterLink to="/kiwi-router" class="text-xs text-green-700 hover:text-green-800 font-medium">Manage routers</RouterLink>
        </div>
        <p class="text-xs text-gray-400 mb-3">Select one router as the default agent target. Its member order and limits control the provider choice.</p>
        <div v-if="!kiwiRouters.length" class="text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg px-4 py-8 text-center">
          No General AI Agent KiwiRouter configured yet.
          <RouterLink to="/kiwi-router" class="text-green-700 hover:text-green-800">Create a router</RouterLink>
          first.
        </div>
        <div v-else class="space-y-3">
          <div v-for="router in kiwiRouters" :key="router.id" class="border rounded-lg bg-white p-4 flex items-start gap-4">
            <button
              :disabled="!router.is_active || selectingRouter !== null"
              :title="router.is_active ? 'Select as the default agent target' : 'Enable this router before selecting it'"
              @click="selectRouter(router)"
              :class="[
                'mt-0.5 w-4 h-4 rounded-full border-2 transition-colors',
                agentTarget.kiwi_router_id === router.id ? 'bg-green-500 border-green-500' : 'bg-white border-gray-300 hover:border-green-400',
              ]"
            />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-gray-900 text-sm">{{ router.name }}</span>
                <span :class="['text-xs px-2 py-0.5 rounded-full font-medium', router.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500']">{{ router.is_active ? 'active' : 'inactive' }}</span>
                <span v-if="agentTarget.kiwi_router_id === router.id" class="text-xs px-2 py-0.5 rounded-full font-medium bg-blue-100 text-blue-700">selected agent</span>
              </div>
              <p class="text-xs text-gray-500 mt-1">{{ router.members.length }} provider agents · Ordered capacity fill</p>
            </div>
            <button
              @click="selectRouter(router)"
              :disabled="!router.is_active || selectingRouter !== null || agentTarget.kiwi_router_id === router.id"
              class="text-xs px-3 py-1.5 border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors disabled:opacity-40"
            >{{ selectingRouter === router.id ? 'Selecting...' : agentTarget.kiwi_router_id === router.id ? 'Selected' : 'Select as agent' }}</button>
          </div>
          <button v-if="agentTarget.mode === 'kiwi_router'" @click="selectDirectAgent" :disabled="selectingRouter !== null" class="text-xs px-3 py-1.5 border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors disabled:opacity-40">{{ selectingRouter === 'direct' ? 'Switching...' : 'Use direct active agent instead' }}</button>
        </div>
      </section>
    </div>

  </div>
</template>
