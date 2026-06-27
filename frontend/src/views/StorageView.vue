<script setup>
import { ref, computed, onMounted } from 'vue'
import { accountsApi } from '@/api'

// ─── state ────────────────────────────────────────────────────────────────────
const accounts = ref([])
const stats    = ref({})   // { [accountId]: { db, media, error? } }
const loading  = ref(true)
const busy     = ref({})   // { [key]: true } e.g. refresh-1, delete-msg-1, …

// confirmation modal
const confirm = ref(null)  // { label, detail, action: async fn }

// per-account restore results / toast
const restoreResult = ref({}) // { [accountId]: { msg, ok } }
const globalResult  = ref(null)

// hidden file inputs (keyed by account id, type)
const fileInputs = ref({})

// ─── helpers ──────────────────────────────────────────────────────────────────
function fmtBytes(b) {
  if (!b) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(1024))
  return `${(b / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${u[i]}`
}
function fmtNum(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
function estDbBytes(db) {
  if (!db) return 0
  return db.message_count * 2048 + db.chat_count * 512 + db.contact_count * 512 + db.sync_log_count * 300
}
function setBusy(key, val) { busy.value = { ...busy.value, [key]: val } }
function isBusy(key)       { return !!busy.value[key] }

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function showConfirm(label, detail, action) {
  confirm.value = { label, detail, action }
}
async function runConfirmed() {
  if (!confirm.value) return
  const fn = confirm.value.action
  confirm.value = null
  await fn()
}

function setRestoreResult(id, msg, ok = true) {
  restoreResult.value = { ...restoreResult.value, [id]: { msg, ok } }
  setTimeout(() => {
    const r = { ...restoreResult.value }
    delete r[id]
    restoreResult.value = r
  }, 6000)
}

// ─── data loading ─────────────────────────────────────────────────────────────
async function fetchStorage(account) {
  setBusy(`refresh-${account.id}`, true)
  try {
    const { data } = await accountsApi.storage(account.id)
    stats.value = { ...stats.value, [account.id]: data }
  } catch {
    stats.value = { ...stats.value, [account.id]: { db: null, media: null, error: true } }
  } finally {
    setBusy(`refresh-${account.id}`, false)
  }
}

async function refreshAll() {
  await Promise.all(accounts.value.map(a => fetchStorage(a)))
}

onMounted(async () => {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data
    await Promise.all(data.map(a => fetchStorage(a)))
  } finally {
    loading.value = false
  }
})

// ─── totals ───────────────────────────────────────────────────────────────────
const totals = computed(() => {
  let dbBytes = 0, mediaBytes = 0, messages = 0, files = 0
  for (const s of Object.values(stats.value)) {
    dbBytes    += estDbBytes(s.db)
    mediaBytes += s.media?.total_bytes || 0
    messages   += s.db?.message_count  || 0
    files      += s.media?.file_count  || 0
  }
  return { dbBytes, mediaBytes, messages, files }
})

// ─── per-account actions ───────────────────────────────────────────────────────
async function doDeleteMessages(account) {
  setBusy(`del-msg-${account.id}`, true)
  try {
    const { data } = await accountsApi.deleteMessages(account.id)
    await fetchStorage(account)
    setRestoreResult(account.id, `Deleted ${fmtNum(data.deleted)} messages`, true)
  } catch {
    setRestoreResult(account.id, 'Delete failed', false)
  } finally {
    setBusy(`del-msg-${account.id}`, false)
  }
}

async function doDeleteMedia(account) {
  setBusy(`del-media-${account.id}`, true)
  try {
    const { data } = await accountsApi.deleteMedia(account.id)
    await fetchStorage(account)
    setRestoreResult(account.id, `Removed ${fmtNum(data.removed_files)} files (${fmtBytes(data.removed_bytes)})`, true)
  } catch {
    setRestoreResult(account.id, 'Delete failed', false)
  } finally {
    setBusy(`del-media-${account.id}`, false)
  }
}

async function doBackupMessages(account) {
  setBusy(`bak-msg-${account.id}`, true)
  try {
    const { data } = await accountsApi.export(account.id)
    triggerDownload(data, `chatlens-messages-${account.id}.json`)
  } catch {
    setRestoreResult(account.id, 'Backup failed', false)
  } finally {
    setBusy(`bak-msg-${account.id}`, false)
  }
}

async function doBackupMedia(account) {
  setBusy(`bak-media-${account.id}`, true)
  try {
    const { data } = await accountsApi.backupMedia(account.id)
    triggerDownload(data, `chatlens-media-${account.id}.zip`)
  } catch {
    setRestoreResult(account.id, 'Backup failed', false)
  } finally {
    setBusy(`bak-media-${account.id}`, false)
  }
}

function pickFile(accountId, type) {
  const key = `${accountId}-${type}`
  if (!fileInputs.value[key]) {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = type === 'msg' ? '.json' : '.zip'
    input.onchange = (e) => handleRestoreFile(accountId, type, e.target.files[0])
    fileInputs.value = { ...fileInputs.value, [key]: input }
  }
  fileInputs.value[key].value = ''
  fileInputs.value[key].click()
}

async function handleRestoreFile(accountId, type, file) {
  if (!file) return
  const account = accounts.value.find(a => a.id === accountId)
  if (!account) return
  const busyKey = type === 'msg' ? `rst-msg-${accountId}` : `rst-media-${accountId}`
  setBusy(busyKey, true)
  try {
    if (type === 'msg') {
      const { data } = await accountsApi.restoreMessages(accountId, file)
      await fetchStorage(account)
      setRestoreResult(accountId, `Restored ${fmtNum(data.restored_messages)} messages in ${data.restored_chats} new chats`, true)
    } else {
      const { data } = await accountsApi.restoreMedia(accountId, file)
      await fetchStorage(account)
      setRestoreResult(accountId, `Extracted ${fmtNum(data.extracted)} files${data.skipped ? `, ${data.skipped} skipped` : ''}`, true)
    }
  } catch (e) {
    const msg = e?.response?.data?.error || 'Restore failed'
    setRestoreResult(accountId, msg, false)
  } finally {
    setBusy(busyKey, false)
  }
}

// ─── global actions ────────────────────────────────────────────────────────────
async function globalDeleteMessages() {
  setBusy('g-del-msg', true)
  try {
    const { data } = await accountsApi.deleteAllMessages()
    await refreshAll()
    globalResult.value = { msg: `Deleted ${fmtNum(data.deleted)} messages across all accounts`, ok: true }
  } catch {
    globalResult.value = { msg: 'Delete failed', ok: false }
  } finally {
    setBusy('g-del-msg', false)
    setTimeout(() => { globalResult.value = null }, 6000)
  }
}

async function globalDeleteMedia() {
  setBusy('g-del-media', true)
  try {
    const { data } = await accountsApi.deleteAllMedia()
    await refreshAll()
    globalResult.value = { msg: `Removed ${fmtNum(data.removed_files)} files (${fmtBytes(data.removed_bytes)}) across all accounts`, ok: true }
  } catch {
    globalResult.value = { msg: 'Delete failed', ok: false }
  } finally {
    setBusy('g-del-media', false)
    setTimeout(() => { globalResult.value = null }, 6000)
  }
}
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
    <div class="max-w-4xl mx-auto px-6 py-8">

      <!-- ── Page header ── -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-semibold text-gray-900">Storage</h1>
          <p class="text-sm text-gray-500 mt-0.5">Disk space, backups and restore per WhatsApp account</p>
        </div>
        <button
          @click="refreshAll"
          :disabled="loading || Object.values(busy).some(v => v)"
          class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': Object.values(busy).some(v => v) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Refresh
        </button>
      </div>

      <!-- ── Global actions ── -->
      <div class="bg-white rounded-xl border border-red-200 overflow-hidden mb-6">
        <div class="px-5 py-3 bg-red-50 border-b border-red-100 flex items-center gap-2">
          <svg class="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          <span class="text-sm font-semibold text-red-700">Global Actions — All Accounts</span>
        </div>

        <!-- Global result toast -->
        <div v-if="globalResult" :class="[
          'mx-5 mt-4 px-4 py-2.5 rounded-lg text-sm font-medium',
          globalResult.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200',
        ]">{{ globalResult.msg }}</div>

        <div class="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Delete all messages -->
          <div class="flex flex-col gap-1.5">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Messages (database)</p>
            <button
              :disabled="isBusy('g-del-msg')"
              @click="showConfirm(
                'Delete All Messages',
                'This will permanently delete every message in the database across all accounts. Chat history cannot be recovered unless you have a backup.',
                globalDeleteMessages
              )"
              class="flex items-center gap-2 justify-center px-4 py-2.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg disabled:opacity-50 transition-colors"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
              {{ isBusy('g-del-msg') ? 'Deleting…' : 'Delete All Messages' }}
            </button>
          </div>

          <!-- Delete all media -->
          <div class="flex flex-col gap-1.5">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Media files (disk)</p>
            <button
              :disabled="isBusy('g-del-media')"
              @click="showConfirm(
                'Delete All Media Files',
                'This will permanently delete all downloaded media files from disk across all accounts. Images, videos, and documents cannot be recovered.',
                globalDeleteMedia
              )"
              class="flex items-center gap-2 justify-center px-4 py-2.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg disabled:opacity-50 transition-colors"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
              {{ isBusy('g-del-media') ? 'Deleting…' : 'Delete All Media' }}
            </button>
          </div>
        </div>
      </div>

      <!-- ── Summary totals ── -->
      <div v-if="!loading" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-xl border border-gray-200 px-4 py-4">
          <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Total Messages</p>
          <p class="text-2xl font-bold text-gray-900 mt-1">{{ fmtNum(totals.messages) }}</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 px-4 py-4">
          <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Media Files</p>
          <p class="text-2xl font-bold text-gray-900 mt-1">{{ fmtNum(totals.files) }}</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 px-4 py-4">
          <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Est. DB Size</p>
          <p class="text-2xl font-bold text-blue-600 mt-1">{{ fmtBytes(totals.dbBytes) }}</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 px-4 py-4">
          <p class="text-xs text-gray-500 font-medium uppercase tracking-wide">Media on Disk</p>
          <p class="text-2xl font-bold text-green-600 mt-1">{{ fmtBytes(totals.mediaBytes) }}</p>
        </div>
      </div>

      <!-- ── Loading ── -->
      <div v-if="loading" class="flex items-center justify-center py-24 text-gray-400">
        <svg class="w-6 h-6 animate-spin mr-3" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
        Loading storage data…
      </div>

      <!-- ── Per-account cards ── -->
      <div v-else class="space-y-4">
        <div v-for="account in accounts" :key="account.id"
          class="bg-white rounded-xl border border-gray-200 overflow-hidden"
        >
          <!-- Card header -->
          <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gray-50">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                <svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
              </div>
              <div>
                <p class="font-semibold text-gray-900 text-sm">
                  {{ account.display_name || account.phone_number || `Account #${account.id}` }}
                </p>
                <p class="text-xs text-gray-500">{{ account.phone_number || `ID: ${account.id}` }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span :class="['text-xs font-medium px-2.5 py-1 rounded-full', account.session_status === 'connected' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500']">
                {{ account.session_status || 'unknown' }}
              </span>
              <button
                @click="fetchStorage(account)"
                :disabled="isBusy(`refresh-${account.id}`)"
                class="p-1.5 text-gray-400 hover:text-gray-600 disabled:opacity-40 transition-colors"
                title="Refresh"
              >
                <svg class="w-4 h-4" :class="{ 'animate-spin': isBusy(`refresh-${account.id}`) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- Stats -->
          <div v-if="isBusy(`refresh-${account.id}`) && !stats[account.id]" class="px-5 py-6 text-center text-sm text-gray-400">
            Loading…
          </div>
          <div v-else-if="stats[account.id]?.error" class="px-5 py-6 text-center text-sm text-red-500">
            Failed to load storage stats
          </div>
          <div v-else-if="stats[account.id]" class="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-gray-100">

            <!-- DB -->
            <div class="px-5 py-4">
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 4.24 2 7v10c0 2.76 4.48 5 10 5s10-2.24 10-5V7c0-2.76-4.48-5-10-5zm0 2c4.42 0 8 1.79 8 4s-3.58 4-8 4-8-1.79-8-4 3.58-4 8-4zm0 16c-4.42 0-8-1.79-8-4v-2.23C5.61 15.17 8.65 16 12 16s6.39-.83 8-2.23V17c0 2.21-3.58 4-8 4z"/></svg>
                Database
              </p>
              <div class="space-y-1.5">
                <div class="flex justify-between text-sm"><span class="text-gray-600">Messages</span><span class="font-semibold">{{ fmtNum(stats[account.id].db.message_count) }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-gray-600">Chats</span><span class="font-semibold">{{ fmtNum(stats[account.id].db.chat_count) }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-gray-600">Contacts</span><span class="font-semibold">{{ fmtNum(stats[account.id].db.contact_count) }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-gray-600">With media</span><span class="font-semibold">{{ fmtNum(stats[account.id].db.media_message_count) }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-gray-600">Activity logs</span><span class="font-semibold">{{ fmtNum(stats[account.id].db.sync_log_count) }}</span></div>
                <div class="border-t border-gray-100 pt-2 flex justify-between text-sm font-medium"><span class="text-gray-700">Est. DB size</span><span class="text-blue-600">{{ fmtBytes(estDbBytes(stats[account.id].db)) }}</span></div>
              </div>
            </div>

            <!-- Media -->
            <div class="px-5 py-4">
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
                Media Files (on disk)
              </p>
              <div class="space-y-1.5">
                <div v-if="stats[account.id].media?.error" class="text-xs text-amber-600 mb-1">{{ stats[account.id].media.error }}</div>
                <div class="flex justify-between text-sm"><span class="text-gray-600">Files stored</span><span class="font-semibold">{{ stats[account.id].media ? fmtNum(stats[account.id].media.file_count) : '—' }}</span></div>
                <div class="flex justify-between text-sm"><span class="text-gray-600">Total size</span><span class="font-semibold text-green-600">{{ stats[account.id].media ? fmtBytes(stats[account.id].media.total_bytes) : '—' }}</span></div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Avg file size</span>
                  <span class="font-semibold">
                    <template v-if="stats[account.id].media?.file_count > 0">{{ fmtBytes(Math.round(stats[account.id].media.total_bytes / stats[account.id].media.file_count)) }}</template>
                    <template v-else>—</template>
                  </span>
                </div>
                <div class="border-t border-gray-100 pt-2 flex justify-between text-sm font-medium"><span class="text-gray-700">Total (DB + media)</span><span>{{ fmtBytes(estDbBytes(stats[account.id].db) + (stats[account.id].media?.total_bytes || 0)) }}</span></div>
              </div>
            </div>
          </div>

          <!-- ── Actions ── -->
          <div v-if="stats[account.id] && !stats[account.id].error" class="border-t border-gray-100 px-5 py-4 space-y-3">

            <!-- Result toast -->
            <div v-if="restoreResult[account.id]" :class="[
              'px-4 py-2.5 rounded-lg text-sm font-medium',
              restoreResult[account.id].ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200',
            ]">{{ restoreResult[account.id].msg }}</div>

            <!-- Backup row -->
            <div>
              <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Backup</p>
              <div class="flex flex-wrap gap-2">
                <button
                  :disabled="isBusy(`bak-msg-${account.id}`)"
                  @click="doBackupMessages(account)"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg disabled:opacity-50 transition-colors"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                  {{ isBusy(`bak-msg-${account.id}`) ? 'Preparing…' : 'Messages (JSON)' }}
                </button>
                <button
                  :disabled="isBusy(`bak-media-${account.id}`)"
                  @click="doBackupMedia(account)"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg disabled:opacity-50 transition-colors"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                  {{ isBusy(`bak-media-${account.id}`) ? 'Zipping…' : 'Media (ZIP)' }}
                </button>
              </div>
            </div>

            <!-- Restore row -->
            <div>
              <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Restore</p>
              <div class="flex flex-wrap gap-2">
                <button
                  :disabled="isBusy(`rst-msg-${account.id}`)"
                  @click="pickFile(account.id, 'msg')"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg disabled:opacity-50 transition-colors"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l4-4m0 0l4 4m-4-4v12"/></svg>
                  {{ isBusy(`rst-msg-${account.id}`) ? 'Restoring…' : 'Restore Messages (JSON)' }}
                </button>
                <button
                  :disabled="isBusy(`rst-media-${account.id}`)"
                  @click="pickFile(account.id, 'media')"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg disabled:opacity-50 transition-colors"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l4-4m0 0l4 4m-4-4v12"/></svg>
                  {{ isBusy(`rst-media-${account.id}`) ? 'Extracting…' : 'Restore Media (ZIP)' }}
                </button>
              </div>
            </div>

            <!-- Delete row -->
            <div>
              <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Delete</p>
              <div class="flex flex-wrap gap-2">
                <button
                  :disabled="isBusy(`del-msg-${account.id}`)"
                  @click="showConfirm(
                    `Delete Messages — ${account.display_name || account.phone_number}`,
                    `This will permanently delete all ${fmtNum(stats[account.id].db.message_count)} messages for this account. This cannot be undone.`,
                    () => doDeleteMessages(account)
                  )"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg disabled:opacity-50 transition-colors"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                  {{ isBusy(`del-msg-${account.id}`) ? 'Deleting…' : 'Delete Messages' }}
                </button>
                <button
                  :disabled="isBusy(`del-media-${account.id}`)"
                  @click="showConfirm(
                    `Delete Media — ${account.display_name || account.phone_number}`,
                    `This will permanently delete ${fmtNum(stats[account.id].media?.file_count || 0)} media files (${fmtBytes(stats[account.id].media?.total_bytes || 0)}) from disk. This cannot be undone.`,
                    () => doDeleteMedia(account)
                  )"
                  class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg disabled:opacity-50 transition-colors"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                  {{ isBusy(`del-media-${account.id}`) ? 'Deleting…' : 'Delete Media' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="accounts.length === 0" class="text-center py-24 text-gray-400 text-sm">
          No accounts found. Add a WhatsApp account on the Sessions page.
        </div>
      </div>

      <p class="text-xs text-gray-400 mt-6 text-center">
        Database size is an estimate (~2 KB/message, ~0.5 KB/chat and contact). Media size is measured directly from disk.
      </p>
    </div>
  </div>

  <!-- ── Confirmation modal ── -->
  <Teleport to="body">
    <div
      v-if="confirm"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="confirm = null"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6 flex flex-col gap-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
            <svg class="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
          </div>
          <div>
            <h2 class="text-base font-semibold text-gray-900">{{ confirm.label }}</h2>
            <p class="text-sm text-gray-500 mt-1">{{ confirm.detail }}</p>
          </div>
        </div>
        <div class="flex gap-3 pt-2">
          <button
            @click="confirm = null"
            class="flex-1 border border-gray-200 text-gray-700 text-sm py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            @click="runConfirmed"
            class="flex-1 bg-red-600 hover:bg-red-700 text-white text-sm py-2 rounded-lg font-medium transition-colors"
          >
            Confirm Delete
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
