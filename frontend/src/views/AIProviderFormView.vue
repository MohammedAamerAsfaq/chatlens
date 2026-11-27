<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { aiProvidersApi } from '@/api/index.js'

// Add / edit one AI provider on its own page (it used to be a popup over the list).
const route = useRoute()
const router = useRouter()

const editId = computed(() => (route.params.id ? Number(route.params.id) : null))
const isEdit = computed(() => editId.value != null)

const meta      = ref({ providers: {}, capabilities: {}, models: {} })
const loading   = ref(true)
const loadError = ref('')
const saving    = ref(false)
const saveError = ref('')

const liveModels        = ref([])  // fetched from provider API
const liveModelMetadata = ref({})  // optional pricing/details by model ID
const liveModelSource   = ref('')  // 'api' | 'fallback' | ''
const fetchModelError   = ref('')
const fetchingModels    = ref(false)

const modelEntry  = ref('list')    // 'list' | 'typed'
const lookup      = ref(null)      // result of Verify for form.model
const lookingUp   = ref(false)
const lookupError = ref('')
const saveRates   = ref(true)

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
    rate_limit_rpm: '',
    rate_limit_tpm: '',
    _originalModel: '',
    _existingExtraConfig: {},
  }
}

// ── Derived ──────────────────────────────────────────────────────────────────

const availableModels = computed(() => {
  if (liveModels.value.length) return liveModels.value
  const key = `${form.value.provider}_${form.value.capability}`
  return meta.value.models[key] || []
})

const availableModelOptions = computed(() => availableModels.value.map(id => ({
  id,
  metadata: liveModelMetadata.value[id] || null,
})))

function modelOptionLabel(option) {
  const metadata = option.metadata
  if (metadata?.input_cost_per_million == null || metadata?.output_cost_per_million == null) return option.id
  return `${option.id} - input ($${Number(metadata.input_cost_per_million).toFixed(4)}/1M) - output ($${Number(metadata.output_cost_per_million).toFixed(4)}/1M)`
}

const providerOptions = computed(() =>
  Object.entries(meta.value.providers).map(([v, l]) => ({ value: v, label: l }))
)

const apiKeyOptional = computed(() => form.value.provider === 'lm_studio')
const baseUrlRequired = computed(() => form.value.provider === 'other')
const canFetchModels = computed(() => {
  if (!form.value.provider || !form.value.capability || fetchingModels.value) return false
  if (apiKeyOptional.value) return true
  return !!(form.value.api_key || isEdit.value)
})

// ── Load ─────────────────────────────────────────────────────────────────────

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [metaRes, providerRes] = await Promise.all([
      aiProvidersApi.meta(),
      isEdit.value ? aiProvidersApi.get(editId.value) : Promise.resolve(null),
    ])
    meta.value = metaRes.data
    if (providerRes) {
      const p = providerRes.data
      const extra = p.extra_config || {}
      form.value = {
        display_name: p.display_name,
        provider:     p.provider,
        capability:   p.capability,
        api_key:      '',
        model:        p.model,
        base_url:     p.base_url || '',
        is_active:    p.is_active,
        rate_limit_rpm: extra.rate_limit_rpm ?? '',
        rate_limit_tpm: extra.rate_limit_tpm ?? '',
        _originalModel: p.model,
        _existingExtraConfig: extra,
      }
      // Editing starts from the saved name, shown as text so it can be read and changed;
      // the fetched list stays one click away.
      modelEntry.value = 'typed'
    }
  } catch (e) {
    loadError.value = e.response?.status === 404 ? 'This provider no longer exists.' : (e.message || 'Unable to load the provider.')
    return
  } finally {
    loading.value = false
  }
  if (isEdit.value) doFetchModels()
}

onMounted(load)

function goBack() {
  if (window.history.state?.back) router.back()
  else router.push({ name: 'ai-providers' })
}

function onProviderChange() {
  // Clear live models and reset model selection when provider/capability changes
  liveModels.value = []
  liveModelMetadata.value = {}
  liveModelSource.value = ''
  fetchModelError.value = ''
  resetLookup()
  if (form.value.provider === 'lm_studio' && !form.value.base_url) {
    form.value.base_url = 'http://localhost:1234/v1'
  }
  const models = meta.value.models[`${form.value.provider}_${form.value.capability}`] || []
  if (models.length && !models.includes(form.value.model)) {
    form.value.model = models[0]
  }
}

function credentialsPayload() {
  const apiKey = form.value.api_key
  return {
    provider:   form.value.provider,
    capability: form.value.capability,
    base_url:   form.value.base_url || '',
    ...(apiKey ? { api_key: apiKey } : isEdit.value ? { config_id: editId.value } : { api_key: '' }),
  }
}

function resetLookup() {
  lookup.value = null
  lookupError.value = ''
}

// A verified result belongs to one name; typing or choosing another makes it stale.
watch(() => form.value.model, model => {
  if (lookup.value && lookup.value.model !== model) resetLookup()
})

const canLookup = computed(() => canFetchModels.value && !lookingUp.value && !!String(form.value.model || '').trim())

async function verifyModel(name = form.value.model) {
  form.value.model = String(name || '').trim()
  if (!form.value.model) return
  lookingUp.value = true
  resetLookup()
  try {
    const { data } = await aiProvidersApi.lookupModel({ ...credentialsPayload(), model: form.value.model })
    form.value.model = data.model
    lookup.value = data
  } catch (e) {
    lookupError.value = e.response?.data?.error || e.message || 'Model lookup failed.'
  } finally {
    lookingUp.value = false
  }
}

function formatTokens(value) {
  if (value == null) return 'not published'
  if (value >= 1_000_000) return `${+(value / 1_000_000).toFixed(2)}M tokens`
  if (value >= 1000) return `${+(value / 1000).toFixed(1)}K tokens`
  return `${value} tokens`
}

function formatRate(value) {
  return value == null ? 'not published' : `$${Number(value).toFixed(4).replace(/\.?0+$/, '')} / 1M tokens`
}

const lookupHasRates = computed(() =>
  lookup.value?.info?.input_cost_per_million != null && lookup.value?.info?.output_cost_per_million != null)

async function doFetchModels() {
  if (!form.value.provider || !form.value.capability) return
  // Cloud providers need either a saved config or an api_key entered in the form.
  // LM Studio Local can be queried without a key.
  if (!form.value.api_key && !isEdit.value && !apiKeyOptional.value) return

  fetchingModels.value  = true
  liveModels.value      = []
  liveModelSource.value = ''
  fetchModelError.value = ''
  try {
    const res = await aiProvidersApi.fetchModels(credentialsPayload())
    liveModels.value      = res.data.models || []
    liveModelMetadata.value = res.data.model_metadata || {}
    liveModelSource.value = res.data.source || ''
    fetchModelError.value = res.data.warning || ''
    // Keep the current model. A name the list doesn't have (typed by hand) stays as typed
    // in the name box rather than being swapped for the first listed model.
    if (liveModels.value.length && !liveModels.value.includes(form.value.model)) {
      if (form.value.model) modelEntry.value = 'typed'
      else form.value.model = liveModels.value[0]
    }
  } catch (e) {
    fetchModelError.value = e.response?.data?.error || e.message || 'Model fetch failed.'
  } finally {
    fetchingModels.value = false
  }
}

async function save() {
  saving.value    = true
  saveError.value = ''
  try {
    const { _originalModel, _existingExtraConfig, rate_limit_rpm, rate_limit_tpm, ...payload } = form.value
    // Merge into whatever this config's extra_config already held (e.g. agent pricing) —
    // extra_config is a single JSON blob server-side, a plain assignment would otherwise
    // silently wipe out unrelated settings already stored there.
    payload.extra_config = {
      ...(_existingExtraConfig || {}),
      rate_limit_rpm: rate_limit_rpm === '' ? null : Number(rate_limit_rpm),
      rate_limit_tpm: rate_limit_tpm === '' ? null : Number(rate_limit_tpm),
    }
    const checked = lookup.value?.verified && lookup.value.model === payload.model ? lookup.value : null
    if (checked?.info) {
      payload.extra_config.model_info = {
        ...checked.info, source: checked.info_source, checked_at: checked.checked_at,
      }
      if (saveRates.value && lookupHasRates.value) {
        payload.extra_config.input_price_per_1m = checked.info.input_cost_per_million
        payload.extra_config.output_price_per_1m = checked.info.output_cost_per_million
      }
    } else if (checked || payload.model !== _originalModel) {
      // Details looked up for another model no longer describe this one.
      delete payload.extra_config.model_info
    }
    if (isEdit.value) {
      // Only send api_key when the user typed a new one.
      if (!payload.api_key) delete payload.api_key
      await aiProvidersApi.update(editId.value, payload)
    } else {
      await aiProvidersApi.create(payload)
    }
    router.push({ name: 'ai-providers' })
  } catch (e) {
    const detail = e.response?.data
    saveError.value = typeof detail === 'object'
      ? Object.values(detail).flat().join(' ')
      : (e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <div class="shrink-0 px-6 py-4 bg-white border-b flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-gray-900">{{ isEdit ? 'Edit Provider' : 'Add Provider' }}</h1>
        <p class="text-sm text-gray-500 mt-0.5">{{ isEdit && form.display_name ? form.display_name : 'Configure an embedding, chat or agent model provider' }}</p>
      </div>
      <button type="button" class="text-sm text-gray-600 hover:text-gray-900" @click="goBack">&larr; Back to AI Providers</button>
    </div>

    <div class="flex-1 overflow-y-auto p-6">
      <div v-if="loading" class="text-gray-400 text-sm">Loading…</div>
      <div v-else-if="loadError" class="max-w-3xl bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3" role="alert">{{ loadError }}</div>

      <form v-else class="provider-form max-w-3xl bg-white border rounded-xl px-6 py-5 space-y-4" @submit.prevent="save">
        <div v-if="saveError" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded px-3 py-2" role="alert">
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
                :disabled="!canFetchModels"
                class="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-gray-50 text-gray-500 disabled:opacity-40 transition-colors"
              >
                {{ fetchingModels ? 'Fetching…' : '↻ Fetch Models' }}
              </button>
            </div>
          </div>
          <p v-if="form.provider === 'lm_studio'" class="text-xs text-gray-500 mb-2">
            Fetch reads from the local LM Studio OpenAI-compatible endpoint, usually http://localhost:1234/v1/models.
          </p>
          <p v-if="fetchModelError" class="text-xs text-red-600 mb-2">
            Model fetch warning: {{ fetchModelError }}
          </p>
          <select v-if="availableModelOptions.length && modelEntry === 'list'" v-model="form.model" required
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
            <option v-for="option in availableModelOptions" :key="option.id" :value="option.id">{{ modelOptionLabel(option) }}</option>
          </select>
          <input v-else v-model="form.model" required
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder="Enter model name or fetch from provider" />
          <div class="flex items-center justify-between gap-2 mt-2">
            <button v-if="availableModelOptions.length" type="button" class="text-xs text-green-700 hover:underline"
              @click="modelEntry = modelEntry === 'list' ? 'typed' : 'list'">
              {{ modelEntry === 'list' ? 'Type a model name instead' : 'Choose from the list instead' }}
            </button>
            <span v-else></span>
            <button type="button" :disabled="!canLookup" @click="verifyModel()"
              title="Check the name with the provider and get its current rates, context window and parameters"
              class="text-xs px-2 py-1 border border-green-600 text-green-700 rounded hover:bg-green-50 disabled:opacity-40 transition-colors">
              {{ lookingUp ? 'Checking…' : 'Verify & get rates' }}
            </button>
          </div>
          <p v-if="lookupError" class="text-xs text-red-600 mt-2" role="alert">{{ lookupError }}</p>
          <div v-if="lookup" class="model-lookup mt-2 border rounded-lg p-3 text-xs space-y-2"
            :class="lookup.verified ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'">
            <p :class="lookup.verified ? 'text-green-800' : 'text-red-700'">
              <strong>{{ lookup.verified ? '✓ Model name is correct.' : '✗ Model name not confirmed.' }}</strong>
              {{ lookup.detail }}
            </p>
            <div v-if="lookup.suggestions?.length" class="flex flex-wrap items-center gap-1">
              <span class="text-gray-600">Did you mean:</span>
              <button v-for="name in lookup.suggestions" :key="name" type="button"
                class="model-lookup__suggestion px-2 py-0.5 bg-white border border-gray-300 rounded font-mono hover:border-green-500"
                @click="verifyModel(name)">{{ name }}</button>
            </div>
            <template v-if="lookup.info">
              <div class="font-medium text-gray-800">{{ lookup.info.name }}</div>
              <dl class="model-lookup__facts grid grid-cols-2 gap-x-3 gap-y-1 text-gray-700">
                <dt class="text-gray-500">Input price</dt><dd>{{ formatRate(lookup.info.input_cost_per_million) }}</dd>
                <dt class="text-gray-500">Output price</dt><dd>{{ formatRate(lookup.info.output_cost_per_million) }}</dd>
                <dt class="text-gray-500">Context window</dt><dd>{{ formatTokens(lookup.info.context_length) }}</dd>
                <dt class="text-gray-500">Longest reply</dt><dd>{{ formatTokens(lookup.info.max_output_tokens) }}</dd>
                <template v-if="lookup.info.input_modalities?.length">
                  <dt class="text-gray-500">Accepts</dt><dd>{{ lookup.info.input_modalities.join(', ') }}</dd>
                </template>
              </dl>
              <div v-if="lookup.info.supported_parameters?.length">
                <div class="text-gray-500 mb-1">Supported parameters</div>
                <div class="flex flex-wrap gap-1">
                  <span v-for="param in lookup.info.supported_parameters" :key="param"
                    class="px-1.5 py-0.5 bg-white border border-gray-200 rounded font-mono">{{ param }}</span>
                </div>
              </div>
              <label v-if="lookup.verified && lookupHasRates" class="flex items-center gap-2 text-gray-700 cursor-pointer">
                <input v-model="saveRates" type="checkbox" class="rounded" />
                Save these rates as this provider's price (used for AI cost figures)
              </label>
            </template>
            <p class="text-gray-500">{{ lookup.info_detail }}</p>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            API Key
            <span v-if="apiKeyOptional" class="text-gray-400 font-normal">(optional for local)</span>
            <span v-if="isEdit" class="text-gray-400 font-normal">(leave blank to keep current)</span>
          </label>
          <input v-model="form.api_key" type="password" autocomplete="new-password"
            :required="!isEdit && !apiKeyOptional"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder="sk-…" />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Base URL
            <span v-if="baseUrlRequired" class="text-gray-400 font-normal">(required for Other)</span>
            <span v-else class="text-gray-400 font-normal">(optional — override for proxies)</span>
          </label>
          <input v-model="form.base_url" type="url" :required="baseUrlRequired"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            :placeholder="form.provider === 'lm_studio' ? 'http://localhost:1234/v1' : 'https://api.example.com/v1'" />
        </div>

        <div class="border border-gray-200 rounded-lg p-3">
          <div class="text-sm font-medium text-gray-700 mb-1">Rate Limiting <span class="text-gray-400 font-normal">(optional)</span></div>
          <p class="text-xs text-gray-500 mb-3">
            Throttles requests to this provider so calls wait their turn instead of failing with a 429 —
            match it to your plan tier (e.g. a free-tier key), then raise or clear it here the moment you upgrade billing.
            Leave blank for no limit.
          </p>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">Requests / minute</label>
              <input v-model="form.rate_limit_rpm" type="number" min="0" placeholder="no limit"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">Tokens / minute</label>
              <input v-model="form.rate_limit_tpm" type="number" min="0" placeholder="no limit"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
            </div>
          </div>
        </div>

        <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input type="checkbox" v-model="form.is_active" class="rounded" />
          Set as active provider for this capability
        </label>

        <div class="flex justify-end gap-3 pt-3 border-t">
          <button type="button" @click="goBack"
            class="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
            Cancel
          </button>
          <button type="submit" :disabled="saving"
            class="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
            {{ saving ? 'Saving…' : (isEdit ? 'Save Changes' : 'Add Provider') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
