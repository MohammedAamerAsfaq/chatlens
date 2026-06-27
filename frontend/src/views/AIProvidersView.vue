<script setup>
import { ref, computed, onMounted } from 'vue'
import { aiProvidersApi } from '@/api/index.js'

// ── State ────────────────────────────────────────────────────────────────────

const providers = ref([])
const meta      = ref({ providers: {}, capabilities: {}, models: {} })
const loading   = ref(false)
const error     = ref('')

const showModal  = ref(false)
const modalMode  = ref('create')   // 'create' | 'edit'
const saving     = ref(false)
const saveError  = ref('')

const testing    = ref({})         // { [id]: 'idle' | 'running' | { ok, ... } }
const deleting   = ref({})

const liveModels      = ref([])    // fetched from provider API
const liveModelSource = ref('')    // 'api' | 'fallback' | ''
const fetchingModels  = ref(false)

const form = ref(emptyForm())

function emptyForm() {
  return {
    display_name: '',
    provider: '',
    capability: '',
    api_key: '',
    model: '',
    base_url: '',
    is_active: false,
    _editId: null,
  }
}

// ── Derived ──────────────────────────────────────────────────────────────────

const embeddingProviders = computed(() => providers.value.filter(p => p.capability === 'embedding'))
const chatProviders      = computed(() => providers.value.filter(p => p.capability === 'chat'))
const agentProviders     = computed(() => providers.value.filter(p => p.capability === 'agent'))

const availableModels = computed(() => {
  if (liveModels.value.length) return liveModels.value
  const key = `${form.value.provider}_${form.value.capability}`
  return meta.value.models[key] || []
})

const providerOptions = computed(() =>
  Object.entries(meta.value.providers).map(([v, l]) => ({ value: v, label: l }))
)

// ── Data ─────────────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  error.value   = ''
  try {
    const [pRes, mRes] = await Promise.all([aiProvidersApi.list(), aiProvidersApi.meta()])
    providers.value = pRes.data
    meta.value      = mRes.data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── Modal ─────────────────────────────────────────────────────────────────────

function openCreate() {
  form.value = emptyForm()
  liveModels.value = []
  liveModelSource.value = ''
  modalMode.value = 'create'
  saveError.value = ''
  showModal.value = true
}

function openEdit(p) {
  form.value = {
    display_name: p.display_name,
    provider:     p.provider,
    capability:   p.capability,
    api_key:      '',
    model:        p.model,
    base_url:     p.base_url || '',
    is_active:    p.is_active,
    _editId:      p.id,
  }
  liveModels.value = []
  liveModelSource.value = ''
  modalMode.value = 'edit'
  saveError.value = ''
  showModal.value = true
  // Auto-fetch models for the existing provider
  doFetchModels()
}

function closeModal() {
  showModal.value = false
}

function onProviderChange() {
  // Clear live models and reset model selection when provider/capability changes
  liveModels.value = []
  liveModelSource.value = ''
  const models = meta.value.models[`${form.value.provider}_${form.value.capability}`] || []
  if (models.length && !models.includes(form.value.model)) {
    form.value.model = models[0]
  }
}

async function doFetchModels() {
  if (!form.value.provider || !form.value.capability) return
  // Need either a saved config id or an api_key entered in the form
  const apiKey  = form.value.api_key
  const editId  = form.value._editId
  if (!apiKey && !editId) return

  fetchingModels.value  = true
  liveModels.value      = []
  liveModelSource.value = ''
  try {
    const payload = {
      provider:   form.value.provider,
      capability: form.value.capability,
      base_url:   form.value.base_url || '',
      ...(apiKey ? { api_key: apiKey } : { config_id: editId }),
    }
    const res = await aiProvidersApi.fetchModels(payload)
    liveModels.value      = res.data.models || []
    liveModelSource.value = res.data.source || ''
    // Keep current model if it's in the list; otherwise default to first
    if (liveModels.value.length && !liveModels.value.includes(form.value.model)) {
      form.value.model = liveModels.value[0]
    }
  } catch {
    // Silent — fall back to hardcoded list
  } finally {
    fetchingModels.value = false
  }
}

async function save() {
  saving.value    = true
  saveError.value = ''
  try {
    const { _editId, ...payload } = form.value
    // On edit, only include api_key if the user filled it in
    if (modalMode.value === 'edit' && !payload.api_key) {
      delete payload.api_key
    }
    if (modalMode.value === 'edit') {
      await aiProvidersApi.update(_editId, payload)
    } else {
      await aiProvidersApi.create(payload)
    }
    showModal.value = false
    await load()
  } catch (e) {
    const detail = e.response?.data
    saveError.value = typeof detail === 'object'
      ? Object.values(detail).flat().join(' ')
      : (e.message || 'Save failed')
  } finally {
    saving.value = false
  }
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
        <p class="text-xs text-gray-400 mb-3">Used for background tasks — enrichment, tagging, summarisation. Assign a faster or cheaper model independently of the user-facing chat provider.</p>
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
    </div>

    <!-- Add / Edit Modal -->
    <Teleport to="body">
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
          <!-- Modal header -->
          <div class="px-6 py-4 border-b flex items-center justify-between">
            <h2 class="text-base font-semibold text-gray-900">
              {{ modalMode === 'create' ? 'Add Provider' : 'Edit Provider' }}
            </h2>
            <button @click="closeModal" class="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
          </div>

          <!-- Form -->
          <form @submit.prevent="save" class="px-6 py-5 space-y-4">
            <div v-if="saveError" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded px-3 py-2">
              {{ saveError }}
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Display name</label>
              <input v-model="form.display_name" required
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="e.g. Voyage AI (embeddings)" />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Provider</label>
                <select v-model="form.provider" required @change="onProviderChange"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                  <option value="" disabled>Select…</option>
                  <option v-for="opt in providerOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Capability</label>
                <select v-model="form.capability" required @change="onProviderChange"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                  <option value="" disabled>Select…</option>
                  <option value="embedding">Embeddings</option>
                  <option value="chat">Chat / Completion</option>
                  <option value="agent">General AI Agent</option>
                </select>
              </div>
            </div>

            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="text-sm font-medium text-gray-700">Model</label>
                <div class="flex items-center gap-2">
                  <span v-if="liveModelSource === 'api'" class="text-xs text-green-600">● live from API</span>
                  <span v-else-if="liveModelSource === 'fallback'" class="text-xs text-amber-500">● suggested (provider has no models API)</span>
                  <button
                    type="button"
                    @click="doFetchModels"
                    :disabled="fetchingModels || !form.value.provider || !form.value.capability || (!form.value.api_key && !form.value._editId)"
                    class="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-gray-50 text-gray-500 disabled:opacity-40 transition-colors"
                  >
                    {{ fetchingModels ? 'Fetching…' : '↻ Fetch Models' }}
                  </button>
                </div>
              </div>
              <select v-if="availableModels.length" v-model="form.model" required
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
              </select>
              <input v-else v-model="form.model" required
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Enter model name or fetch from provider" />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                API Key
                <span v-if="modalMode === 'edit'" class="text-gray-400 font-normal">(leave blank to keep current)</span>
              </label>
              <input v-model="form.api_key" type="password" autocomplete="new-password"
                :required="modalMode === 'create'"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="sk-…" />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                Base URL <span class="text-gray-400 font-normal">(optional — override for proxies)</span>
              </label>
              <input v-model="form.base_url" type="url"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="https://api.voyageai.com/v1" />
            </div>

            <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input type="checkbox" v-model="form.is_active" class="rounded" />
              Set as active provider for this capability
            </label>

            <!-- Footer -->
            <div class="flex justify-end gap-3 pt-2 border-t">
              <button type="button" @click="closeModal"
                class="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
                Cancel
              </button>
              <button type="submit" :disabled="saving"
                class="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
                {{ saving ? 'Saving…' : (modalMode === 'create' ? 'Add Provider' : 'Save Changes') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<!-- ProviderCard sub-component (defined inline via script setup via defineOptions pattern isn't available
     in Vue 3 SFC without <script> blocks, so we use a simple local component approach) -->
<script>
// Inline component for provider cards
const ProviderCard = {
  props: ['provider', 'testResult', 'deleting'],
  emits: ['edit', 'toggle-active', 'test', 'delete'],
  template: `
    <div class="border rounded-lg bg-white p-4 flex items-start gap-4">
      <!-- Active indicator -->
      <div class="pt-0.5">
        <button
          @click="$emit('toggle-active')"
          :title="provider.is_active ? 'Click to deactivate' : 'Click to activate'"
          :class="[
            'w-4 h-4 rounded-full border-2 transition-colors',
            provider.is_active
              ? 'bg-green-500 border-green-500'
              : 'bg-white border-gray-300 hover:border-green-400',
          ]"
        />
      </div>

      <!-- Info -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-medium text-gray-900 text-sm">{{ provider.display_name }}</span>
          <span :class="['text-xs px-2 py-0.5 rounded-full font-medium', provider.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500']">
            {{ provider.is_active ? 'active' : 'inactive' }}
          </span>
        </div>
        <div class="text-xs text-gray-500 mt-1 space-x-3">
          <span>{{ provider.provider_label }}</span>
          <span>·</span>
          <span class="font-mono">{{ provider.model }}</span>
          <span>·</span>
          <span class="font-mono">{{ provider.api_key_masked }}</span>
        </div>
        <!-- Test result -->
        <div v-if="testResult && testResult !== 'running'" class="mt-2 text-xs">
          <span v-if="testResult.ok" class="text-green-600">
            ✓ Connected
            <template v-if="testResult.dimensions"> · {{ testResult.dimensions }} dims</template>
            <template v-if="testResult.response"> · "{{ testResult.response }}"</template>
          </span>
          <span v-else class="text-red-600">✗ {{ testResult.error }}</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-2 shrink-0">
        <button
          @click="$emit('test')"
          :disabled="testResult === 'running'"
          class="text-xs px-3 py-1.5 border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors disabled:opacity-40"
        >
          {{ testResult === 'running' ? 'Testing…' : 'Test' }}
        </button>
        <button
          @click="$emit('edit')"
          class="text-xs px-3 py-1.5 border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors"
        >
          Edit
        </button>
        <button
          @click="$emit('delete')"
          :disabled="deleting"
          class="text-xs px-3 py-1.5 border border-red-200 rounded hover:bg-red-50 text-red-600 transition-colors disabled:opacity-40"
        >
          {{ deleting ? '…' : 'Delete' }}
        </button>
      </div>
    </div>
  `,
}

export default { components: { ProviderCard } }
</script>
