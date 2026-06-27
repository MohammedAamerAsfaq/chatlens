<script setup>
import { ref, watch, computed } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import { chatsApi } from '@/api'

const props = defineProps({ open: Boolean })
const emit  = defineEmits(['close'])

const store = useConversationsStore()
const info      = ref(null)
const groupInfo = ref(null)
const loading   = ref(false)

const avatarColors = [
  'bg-purple-500','bg-blue-500','bg-green-600','bg-yellow-500',
  'bg-pink-500','bg-indigo-500','bg-teal-500','bg-orange-500',
]
function avatarColor(name) {
  return avatarColors[(name || '?').charCodeAt(0) % avatarColors.length]
}
function avatarLetter(name) {
  return (name || '?').replace(/^\+/, '')[0].toUpperCase()
}

const isGroup = computed(() => store.selectedChat?.wa_chat_id?.endsWith('@g.us'))
const isLid   = computed(() => info.value?.wa_chat_id?.endsWith('@lid'))

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
}
function fmtNum(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

watch(() => [props.open, store.selectedChatId], async ([open, chatId]) => {
  if (!open || !chatId) { info.value = null; groupInfo.value = null; return }
  loading.value = true
  info.value = null
  groupInfo.value = null
  try {
    const { data } = await chatsApi.info(chatId)
    info.value = data
    if (data.wa_chat_id?.endsWith('@g.us')) {
      // Load group members in parallel — non-fatal if worker is offline
      chatsApi.groupInfo(chatId)
        .then(r => { groupInfo.value = r.data })
        .catch(() => {})
    }
  } catch {
    info.value = null
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>

<template>
  <div class="w-80 h-full flex flex-col bg-white border-l border-gray-200 overflow-hidden">

    <!-- Header -->
    <div class="bg-[#f0f2f5] px-4 py-3.5 flex items-center gap-4 shrink-0 border-b border-gray-200">
      <button @click="emit('close')" class="text-gray-500 hover:text-gray-700 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
      <span class="font-semibold text-gray-800 text-sm">
        {{ isGroup ? 'Group info' : 'Contact info' }}
      </span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-400 text-sm">
      Loading…
    </div>

    <!-- No chat -->
    <div v-else-if="!info" class="flex-1 flex items-center justify-center text-gray-400 text-sm">
      No chat selected
    </div>

    <div v-else class="flex-1 overflow-y-auto">

      <!-- ── Avatar + name ───────────────────────────────────────── -->
      <div class="flex flex-col items-center px-6 py-8 bg-white border-b border-gray-100">

        <!-- Group avatar -->
        <div v-if="isGroup"
          class="w-24 h-24 rounded-full bg-gray-200 flex items-center justify-center mb-4 shadow-inner"
        >
          <svg class="w-12 h-12 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
          </svg>
        </div>

        <!-- Individual avatar -->
        <div v-else
          :class="['w-24 h-24 rounded-full flex items-center justify-center text-white font-bold text-3xl mb-4', avatarColor(info.display_name)]"
        >{{ avatarLetter(info.display_name) }}</div>

        <!-- Name -->
        <p class="text-lg font-semibold text-gray-900 text-center">{{ info.display_name }}</p>

        <!-- Group subtitle -->
        <p v-if="isGroup" class="text-sm text-gray-500 mt-0.5">
          Group
          <span v-if="groupInfo" class="text-green-600 font-medium"> · {{ groupInfo.member_count }} members</span>
        </p>

        <!-- Individual phone -->
        <p v-if="!isGroup && info.contact?.phone_number" class="text-sm text-gray-500 mt-0.5">
          +{{ info.contact.phone_number }}
        </p>
        <p v-if="isLid && !info.contact?.phone_number"
          class="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-3 py-1 mt-2"
        >Phone not resolved — reconnect to try again</p>

        <!-- Business badge -->
        <span v-if="info.contact?.is_business"
          class="mt-2 inline-flex items-center gap-1 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-0.5 rounded-full"
        >
          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M20 6h-2.18c.07-.44.18-.88.18-1.34C18 2.54 15.46 0 12 0S6 2.54 6 4.66c0 .46.11.9.18 1.34H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-8-4c1.68 0 3.34.83 3.34 2.66 0 .63-.19 1.23-.51 1.76A3.48 3.48 0 0112 7.34a3.48 3.48 0 01-2.83-1.08A3.27 3.27 0 018.66 4.5C8.66 2.83 10.32 2 12 2z"/></svg>
          Business
        </span>
      </div>

      <!-- ── Group description ───────────────────────────────────── -->
      <div v-if="isGroup && groupInfo?.description" class="px-5 py-4 border-b border-gray-100">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Description</p>
        <p class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{{ groupInfo.description }}</p>
      </div>

      <!-- ── Announce-only notice ────────────────────────────────── -->
      <div v-if="isGroup && groupInfo?.announce" class="mx-5 mt-4 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 flex items-center gap-2">
        <svg class="w-4 h-4 text-amber-500 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1a9 9 0 100 18A9 9 0 0012 1zm1 13h-2v-2h2v2zm0-4h-2V7h2v3z"/></svg>
        <p class="text-xs text-amber-700">Only admins can send messages</p>
      </div>

      <!-- ── Individual contact details ─────────────────────────── -->
      <div v-if="!isGroup && info.contact && (info.contact.push_name || info.contact.display_name)"
        class="px-5 py-4 border-b border-gray-100 space-y-2"
      >
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Names</p>
        <div v-if="info.contact.display_name" class="flex justify-between text-sm">
          <span class="text-gray-500">Saved as</span>
          <span class="text-gray-800 font-medium">{{ info.contact.display_name }}</span>
        </div>
        <div v-if="info.contact.push_name" class="flex justify-between text-sm">
          <span class="text-gray-500">WhatsApp name</span>
          <span class="text-gray-800 font-medium">{{ info.contact.push_name }}</span>
        </div>
      </div>

      <!-- ── WhatsApp / Group ID ────────────────────────────────── -->
      <div class="px-5 py-4 border-b border-gray-100">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
          {{ isGroup ? 'Group ID' : 'WhatsApp ID' }}
        </p>
        <p class="text-sm text-gray-700 font-mono break-all">{{ info.wa_chat_id }}</p>
      </div>

      <!-- ── Media counts ───────────────────────────────────────── -->
      <div class="px-5 py-4 border-b border-gray-100">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Messages</p>
        <div class="grid grid-cols-2 gap-3">
          <div class="bg-gray-50 rounded-lg px-3 py-2.5 text-center">
            <p class="text-xl font-bold text-gray-900">{{ fmtNum(info.message_count) }}</p>
            <p class="text-xs text-gray-500 mt-0.5">Total</p>
          </div>
          <div class="bg-gray-50 rounded-lg px-3 py-2.5 text-center">
            <p class="text-xl font-bold text-green-600">{{ fmtNum(info.media_counts.total) }}</p>
            <p class="text-xs text-gray-500 mt-0.5">With media</p>
          </div>
        </div>
      </div>

      <!-- Media breakdown -->
      <div v-if="info.media_counts.total > 0" class="px-5 py-4 border-b border-gray-100">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Media breakdown</p>
        <div class="space-y-2">
          <div v-for="[type, icon, color] in [
            ['image','🖼️','text-blue-600'],['video','🎥','text-purple-600'],
            ['audio','🎵','text-green-600'],['document','📄','text-yellow-600'],
            ['sticker','😊','text-pink-600'],
          ]" :key="type" v-show="info.media_counts[type] > 0"
            class="flex items-center justify-between text-sm"
          >
            <span class="flex items-center gap-2 text-gray-600 capitalize"><span>{{ icon }}</span> {{ type }}s</span>
            <span :class="['font-semibold', color]">{{ fmtNum(info.media_counts[type]) }}</span>
          </div>
        </div>
      </div>

      <!-- ── Date range ─────────────────────────────────────────── -->
      <div class="px-5 py-4 border-b border-gray-100">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Date range</p>
        <div class="space-y-2">
          <div class="flex justify-between text-sm">
            <span class="text-gray-500">First message</span>
            <span class="text-gray-800 font-medium">{{ fmt(info.first_message_at) }}</span>
          </div>
          <div class="flex justify-between text-sm">
            <span class="text-gray-500">Last message</span>
            <span class="text-gray-800 font-medium">{{ fmt(info.last_message_at) }}</span>
          </div>
        </div>
      </div>

      <!-- ── Group members ──────────────────────────────────────── -->
      <div v-if="isGroup" class="px-5 py-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Active participants
              <span v-if="groupInfo" class="normal-case font-normal">
                ({{ groupInfo.active_senders }} of {{ groupInfo.member_count }})
              </span>
            </p>
            <p class="text-xs text-gray-400 mt-0.5">People who have sent at least one message</p>
          </div>
        </div>

        <!-- Loading members -->
        <div v-if="!groupInfo" class="flex justify-center py-4">
          <span class="text-xs text-gray-400">Loading members…</span>
        </div>

        <!-- Member list -->
        <div v-else class="space-y-1">
          <div
            v-for="p in groupInfo.participants"
            :key="p.jid"
            class="flex items-center gap-3 py-1.5 rounded-lg hover:bg-gray-50 -mx-1 px-1"
          >
            <!-- Avatar -->
            <div :class="['w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-semibold shrink-0',
              avatarColor(p.display_name || p.phone || '?')]"
            >
              {{ avatarLetter(p.display_name || p.phone || '?') }}
            </div>

            <!-- Name + phone -->
            <div class="flex-1 min-w-0">
              <p class="text-sm text-gray-800 font-medium truncate">
                {{ p.display_name || (p.phone ? `+${p.phone}` : 'Unknown member') }}
              </p>
              <p v-if="p.display_name && p.phone" class="text-xs text-gray-400 truncate">+{{ p.phone }}</p>
            </div>

            <!-- Admin badge -->
            <span v-if="p.is_super_admin"
              class="text-[10px] font-semibold text-green-700 bg-green-50 border border-green-200 px-1.5 py-0.5 rounded shrink-0"
            >Superadmin</span>
            <span v-else-if="p.is_admin"
              class="text-[10px] font-semibold text-gray-600 bg-gray-100 border border-gray-200 px-1.5 py-0.5 rounded shrink-0"
            >Admin</span>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
