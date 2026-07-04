<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useAccountsStore } from '@/stores/accounts'
import { accountsApi } from '@/api'

const props = defineProps({ account: Object })
const emit = defineEmits(['show-qr', 'refresh'])
const store = useAccountsStore()

const showSettings      = ref(false)
const showDeleteConfirm = ref(false)
const exportBeforeDelete = ref(true)
const deleting          = ref(false)
const savingSettings    = ref(false)

// Local copy of settings for editing
const localSettings = ref({
  sync_history:            props.account.sync_history ?? true,
  history_days:            props.account.history_days ?? '',
  idle_disconnect_minutes: props.account.idle_disconnect_minutes ?? 0,
  auto_download_media:     props.account.auto_download_media ?? true,
  ai_parsing_enabled:      props.account.ai_parsing_enabled ?? false,
})

const historyOptions = [
  { label: 'All time',     value: '' },
  { label: 'Last 1 day',   value: 1 },
  { label: 'Last 1 month', value: 30 },
  { label: 'Last 3 months',value: 90 },
  { label: 'Last 6 months',value: 180 },
  { label: 'Last 1 year',  value: 365 },
]

const statusConfig = {
  pending_qr:   { label: 'Pending QR',   cls: 'bg-yellow-100 text-yellow-800' },
  qr_generated: { label: 'QR Generated', cls: 'bg-blue-100 text-blue-800' },
  connected:    { label: 'Connected',    cls: 'bg-green-100 text-green-800' },
  disconnected: { label: 'Disconnected', cls: 'bg-gray-100 text-gray-600' },
  logged_out:   { label: 'Logged Out',   cls: 'bg-red-100 text-red-700' },
  error:        { label: 'Error',        cls: 'bg-red-100 text-red-700' },
}

function statusFor(s) {
  return statusConfig[s] || { label: s, cls: 'bg-gray-100 text-gray-600' }
}

function formatDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString()
}

async function connect() {
  await store.startSession(props.account.id)
  emit('show-qr', props.account.id)
}

async function disconnect() {
  await store.disconnect(props.account.id)
  emit('refresh')
}

async function saveSettings() {
  savingSettings.value = true
  try {
    await store.updateSettings(props.account.id, {
      sync_history:            localSettings.value.sync_history,
      history_days:            localSettings.value.history_days === '' ? null : Number(localSettings.value.history_days),
      idle_disconnect_minutes: Number(localSettings.value.idle_disconnect_minutes) || 0,
      auto_download_media:     localSettings.value.auto_download_media,
      ai_parsing_enabled:      localSettings.value.ai_parsing_enabled,
    })
    showSettings.value = false
  } finally {
    savingSettings.value = false
  }
}

async function confirmDelete() {
  deleting.value = true
  try {
    if (exportBeforeDelete.value) {
      await store.exportAccount(
        props.account.id,
        `chatlens-${props.account.phone_number || props.account.id}.json`,
      )
    }
    await store.deleteAccount(props.account.id)
    emit('refresh')
  } finally {
    deleting.value = false
    showDeleteConfirm.value = false
  }
}

// ── History sync progress ─────────────────────────────────────────────────────

const syncProgress = ref(null)   // { syncing, total_synced, total_processed, batch_count }
const syncDone     = ref(false)  // true briefly after sync finishes
const syncFinished = ref(false)  // permanently true after the done badge fades
let syncPollTimer  = null
let syncDoneTimer  = null

// null      = nothing to show (sync_history off, disconnected, or already done+faded)
// 'awaiting'= connected + sync_history on, but no batches from WhatsApp yet
// 'syncing' = batches actively arriving (Django has recent history_sync logs)
// 'done'    = sync just completed (shown for 8s)
const syncState = computed(() => {
  if (syncFinished.value) return null
  if (syncDone.value) return 'done'
  if (!props.account.sync_history) return null
  if (props.account.session_status !== 'connected') return null
  if (syncProgress.value?.syncing) return 'syncing'
  // batch_count > 0 but not currently syncing = history batch already done before this page load
  if (syncProgress.value && syncProgress.value.batch_count > 0) return null
  // Live messages arriving means the connection is active even without a history batch
  if (syncProgress.value?.has_live_messages) return null
  return 'awaiting'
})

async function fetchSyncProgress() {
  if (!props.account.sync_history) return
  try {
    const { data } = await accountsApi.syncProgress(props.account.id)
    const alreadyComplete = syncProgress.value?.is_complete
    syncProgress.value = data

    // is_complete comes from Baileys' own isLatest flag on the final history chunk —
    // authoritative, and set even when that chunk had zero messages after the
    // history_days filter. This replaces the old "no new batches for 30s" heuristic,
    // which could never fire for an account whose entire history sync filtered down
    // to nothing (no batches ever arrived to go idle from).
    if (!alreadyComplete && data.is_complete) {
      syncDone.value = true
      clearInterval(syncPollTimer)
      syncPollTimer = null
      syncDoneTimer = setTimeout(() => {
        syncDone.value = false
        syncProgress.value = null
        syncFinished.value = true
      }, 8000)
    }
  } catch {}
}

function startSyncPolling() {
  clearInterval(syncPollTimer)
  syncPollTimer = null
  clearTimeout(syncDoneTimer)
  syncDoneTimer = null
  syncDone.value     = false
  syncFinished.value = false
  syncProgress.value = null

  if (props.account.sync_history) {
    fetchSyncProgress()
    syncPollTimer = setInterval(fetchSyncProgress, 4000)
  }
}

watch(
  () => props.account.session_status,
  (status) => {
    if (status === 'connected') {
      startSyncPolling()
    } else {
      clearInterval(syncPollTimer)
      syncPollTimer = null
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  clearInterval(syncPollTimer)
  clearTimeout(syncDoneTimer)
})
</script>

<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col gap-3">

    <!-- Header -->
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="font-semibold text-gray-900 truncate">
          {{ account.display_name || 'Unnamed Account' }}
        </p>
        <p class="text-sm text-gray-500">{{ account.phone_number || 'No phone yet' }}</p>
      </div>
      <span :class="['shrink-0 text-xs font-medium px-2 py-1 rounded-full', statusFor(account.session_status).cls]">
        {{ statusFor(account.session_status).label }}
      </span>
    </div>

    <p class="text-xs text-gray-400">Last connected: {{ formatDate(account.last_connected_at) }}</p>

    <!-- History sync progress — three states -->
    <div v-if="syncState" class="flex flex-col gap-1.5 border border-gray-100 rounded-lg p-3 bg-gray-50">

      <!-- State: awaiting — WhatsApp is negotiating sync keys (no batches yet) -->
      <template v-if="syncState === 'awaiting'">
        <div class="flex items-center gap-2 text-xs text-gray-600 font-medium">
          <div class="w-3 h-3 rounded-full border-2 border-gray-200 border-t-green-500 animate-spin shrink-0" />
          Waiting for history sync to begin…
        </div>
        <div class="h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div class="h-full bg-green-300 w-full rounded-full animate-pulse" />
        </div>
        <p class="text-xs text-gray-400 leading-relaxed">
          WhatsApp is negotiating sync keys. Large accounts can take <strong>10–30 minutes</strong>
          before messages start arriving. Keep this session connected.
        </p>
      </template>

      <!-- State: syncing — batches actively arriving from Django -->
      <template v-else-if="syncState === 'syncing'">
        <div class="flex items-center justify-between text-xs">
          <span class="text-gray-700 font-medium">
            Syncing history…
            <strong>{{ syncProgress.total_synced.toLocaleString() }}</strong> messages so far
          </span>
          <span class="text-gray-400">{{ syncProgress.batch_count }} batch{{ syncProgress.batch_count !== 1 ? 'es' : '' }}</span>
        </div>
        <div class="h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div class="h-full bg-green-500 rounded-full animate-sync-bar" />
        </div>
      </template>

      <!-- State: done — briefly shown after sync finishes -->
      <template v-else-if="syncState === 'done'">
        <div class="flex items-center justify-between text-xs">
          <span class="text-green-600 font-medium">
            <template v-if="syncProgress.total_synced > 0">
              ✓ Sync complete — <strong>{{ syncProgress.total_synced.toLocaleString() }}</strong> messages imported
            </template>
            <template v-else>
              ✓ Sync complete — no messages found in your sync window
            </template>
          </span>
          <span class="text-gray-400">{{ syncProgress.batch_count }} batch{{ syncProgress.batch_count !== 1 ? 'es' : '' }}</span>
        </div>
        <div class="h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div class="h-full bg-green-500 w-full rounded-full" />
        </div>
      </template>

    </div>

    <!-- Action buttons -->
    <div class="flex gap-2">
      <button
        v-if="['disconnected', 'pending_qr', 'logged_out', 'error'].includes(account.session_status)"
        @click="connect"
        class="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        Connect
      </button>

      <button
        v-if="account.session_status === 'qr_generated'"
        @click="emit('show-qr', account.id)"
        class="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        Show QR
      </button>

      <button
        v-if="account.session_status === 'connected'"
        @click="disconnect"
        class="flex-1 bg-red-500 hover:bg-red-600 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        Disconnect
      </button>

      <button
        @click="showSettings = !showSettings"
        :class="[
          'px-3 py-1.5 rounded-lg text-sm transition-colors border',
          showSettings
            ? 'bg-gray-100 border-gray-300 text-gray-700'
            : 'border-gray-200 text-gray-500 hover:bg-gray-50',
        ]"
      >
        Settings {{ showSettings ? '▲' : '▼' }}
      </button>
    </div>

    <!-- Settings panel -->
    <div v-if="showSettings" class="border-t border-gray-100 pt-3 flex flex-col gap-4">

      <!-- ── Sync history ───────────────────────── -->
      <div class="flex flex-col gap-2">
        <p class="text-xs text-gray-400 uppercase tracking-wide font-medium">Message History</p>

        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700">Sync message history</span>
          <button
            @click="localSettings.sync_history = !localSettings.sync_history"
            :class="['relative w-10 h-5 rounded-full transition-colors', localSettings.sync_history ? 'bg-green-500' : 'bg-gray-300']"
          >
            <span :class="['absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform', localSettings.sync_history ? 'translate-x-5' : 'translate-x-0.5']" />
          </button>
        </div>

        <div v-if="localSettings.sync_history">
          <label class="text-xs text-gray-500 block mb-1">Sync history from</label>
          <select
            v-model="localSettings.history_days"
            class="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-500"
          >
            <option v-for="opt in historyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <p class="text-xs text-gray-400 mt-1">Only applies on next connection. Existing data is not removed.</p>
        </div>
      </div>

      <!-- ── Media & AI ────────────────────────── -->
      <div class="flex flex-col gap-2">
        <p class="text-xs text-gray-400 uppercase tracking-wide font-medium">Media &amp; AI</p>

        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm text-gray-700">Auto-download media</span>
            <p class="text-xs text-gray-400 mt-0.5">Images, documents, audio received in chats</p>
          </div>
          <button
            @click="localSettings.auto_download_media = !localSettings.auto_download_media"
            :class="['relative w-10 h-5 rounded-full transition-colors shrink-0', localSettings.auto_download_media ? 'bg-green-500' : 'bg-gray-300']"
          >
            <span :class="['absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform', localSettings.auto_download_media ? 'translate-x-5' : 'translate-x-0.5']" />
          </button>
        </div>

        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm text-gray-700">AI inquiry parsing</span>
            <p class="text-xs text-gray-400 mt-0.5">Default for contacts with no override</p>
          </div>
          <button
            @click="localSettings.ai_parsing_enabled = !localSettings.ai_parsing_enabled"
            :class="['relative w-10 h-5 rounded-full transition-colors shrink-0', localSettings.ai_parsing_enabled ? 'bg-green-500' : 'bg-gray-300']"
          >
            <span :class="['absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform', localSettings.ai_parsing_enabled ? 'translate-x-5' : 'translate-x-0.5']" />
          </button>
        </div>
      </div>

      <!-- ── Connection ────────────────────────── -->
      <div class="flex flex-col gap-2">
        <p class="text-xs text-gray-400 uppercase tracking-wide font-medium">Connection</p>
        <div>
          <label class="text-xs text-gray-500 block mb-1">Auto-disconnect after idle (minutes, 0 = disabled)</label>
          <input
            v-model.number="localSettings.idle_disconnect_minutes"
            type="number"
            min="0"
            step="5"
            placeholder="0"
            class="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-500"
          />
          <p class="text-xs text-gray-400 mt-1">Session stays offline until you manually reconnect. No QR needed.</p>
        </div>
      </div>

      <button
        @click="saveSettings"
        :disabled="savingSettings"
        class="w-full bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        {{ savingSettings ? 'Saving…' : 'Save Settings' }}
      </button>
    </div>

    <!-- Delete button -->
    <div class="border-t border-gray-100 pt-2">
      <button
        @click="showDeleteConfirm = true"
        class="w-full text-sm text-red-500 hover:text-red-700 hover:bg-red-50 py-1.5 rounded-lg transition-colors"
      >
        Delete Account
      </button>
    </div>
  </div>

  <!-- Delete confirmation dialog -->
  <Teleport to="body">
    <div
      v-if="showDeleteConfirm"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="showDeleteConfirm = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 flex flex-col gap-4">
        <h2 class="text-lg font-semibold text-gray-900">Delete Account</h2>
        <p class="text-sm text-gray-600">
          This will permanently delete
          <strong>{{ account.display_name || account.phone_number || 'this account' }}</strong>
          and all its chats and messages. This cannot be undone.
        </p>

        <label class="flex items-start gap-3 cursor-pointer">
          <input v-model="exportBeforeDelete" type="checkbox" class="mt-0.5 w-4 h-4 rounded accent-green-600" />
          <span class="text-sm text-gray-700">Export chat history as JSON before deleting</span>
        </label>

        <div class="flex gap-3 mt-2">
          <button
            @click="showDeleteConfirm = false"
            class="flex-1 border border-gray-200 text-gray-700 text-sm py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            @click="confirmDelete"
            :disabled="deleting"
            class="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg transition-colors"
          >
            {{ deleting ? (exportBeforeDelete ? 'Exporting…' : 'Deleting…') : 'Delete Account' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
@keyframes sync-slide {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
.animate-sync-bar {
  width: 40%;
  animation: sync-slide 1.6s ease-in-out infinite;
}
</style>
