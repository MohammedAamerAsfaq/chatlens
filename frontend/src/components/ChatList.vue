<script setup>
import { ref, computed } from 'vue'
import { useConversationsStore } from '@/stores/conversations'

const store = useConversationsStore()
const activeFilter = ref('all')

const tabs = [
  { key: 'all',    label: 'All' },
  { key: 'unread', label: 'Unread' },
  { key: 'direct', label: 'Direct' },
  { key: 'groups', label: 'Groups' },
]

function chatKind(waId) {
  if (waId?.endsWith('@g.us')) return 'group'
  if (waId?.endsWith('@broadcast')) return 'broadcast'
  return 'direct'
}

const displayedChats = computed(() => {
  let list = store.filteredChats
  if (activeFilter.value === 'unread') list = list.filter(c => c.unread_count > 0)
  else if (activeFilter.value === 'groups') list = list.filter(c => chatKind(c.wa_chat_id) === 'group')
  else if (activeFilter.value === 'direct') list = list.filter(c => chatKind(c.wa_chat_id) === 'direct')
  return list
})

const avatarColors = [
  'bg-purple-500','bg-blue-500','bg-green-600','bg-yellow-500',
  'bg-pink-500','bg-indigo-500','bg-teal-500','bg-orange-500',
]
function avatarColor(name) {
  return avatarColors[(name || '?').charCodeAt(0) % avatarColors.length]
}
function avatarLetter(name) {
  const clean = (name || '?').replace(/^\+/, '')
  return (clean || '?')[0].toUpperCase()
}

function formatTime(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  if (d.toDateString() === now.toDateString())
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const diff = (now - d) / 86400000
  if (diff < 7) return d.toLocaleDateString([], { weekday: 'short' })
  return d.toLocaleDateString([], { day: '2-digit', month: '2-digit', year: '2-digit' })
}
</script>

<template>
  <div class="flex flex-col bg-white border-r border-gray-200 overflow-hidden">

    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-200">
      <span class="font-semibold text-gray-800 text-sm">
        {{ store.selectedAccount?.display_name || store.selectedAccount?.phone_number || 'Chats' }}
      </span>
      <span class="text-xs text-gray-400">{{ store.chats.length }} chats</span>
    </div>

    <!-- Search -->
    <div class="px-3 py-2 border-b border-gray-100">
      <div class="flex items-center bg-gray-100 rounded-full px-3 py-2 gap-2">
        <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
        </svg>
        <input
          v-model="store.searchQuery"
          type="text"
          placeholder="Search or start new chat"
          class="bg-transparent text-sm w-full focus:outline-none text-gray-700 placeholder-gray-400"
        />
      </div>
    </div>

    <!-- Filter tabs -->
    <div class="flex border-b border-gray-100 shrink-0">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeFilter = tab.key"
        :class="[
          'flex-1 text-xs py-2.5 font-medium transition-colors border-b-2',
          activeFilter === tab.key
            ? 'border-green-500 text-green-600'
            : 'border-transparent text-gray-400 hover:text-gray-600',
        ]"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Chat list -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="store.loadingChats" class="text-center text-gray-400 py-12 text-sm">
        Loading...
      </div>

      <div v-else-if="displayedChats.length === 0" class="text-center text-gray-400 py-12 text-sm px-4">
        <p>No conversations here</p>
      </div>

      <button
        v-for="chat in displayedChats"
        :key="chat.id"
        @click="store.selectChat(chat.id)"
        :class="[
          'w-full text-left flex items-center gap-3 px-3 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors',
          store.selectedChatId === chat.id ? 'bg-gray-100' : '',
        ]"
      >
        <!-- Avatar -->
        <div class="relative shrink-0">
          <div v-if="chatKind(chat.wa_chat_id) === 'group'"
            class="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center"
          >
            <svg class="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
            </svg>
          </div>
          <div v-else
            :class="['w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold text-lg', avatarColor(chat.display_name)]"
          >
            {{ avatarLetter(chat.display_name) }}
          </div>
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between mb-0.5">
            <span :class="['text-sm truncate', chat.unread_count > 0 ? 'font-semibold text-gray-900' : 'font-medium text-gray-800']">
              {{ chat.display_name }}
            </span>
            <span :class="['text-xs shrink-0 ml-2', chat.unread_count > 0 ? 'text-green-600 font-medium' : 'text-gray-400']">
              {{ formatTime(chat.last_message_at) }}
            </span>
          </div>
          <div class="flex items-center justify-between gap-1">
            <p class="text-xs text-gray-500 truncate flex items-center gap-1">
              <span v-if="chat.last_message_direction === 'outbound'" class="text-gray-400">
                <svg class="w-3 h-3 inline text-blue-500" fill="currentColor" viewBox="0 0 16 11">
                  <path d="M11.071.653a.75.75 0 0 1 .052 1.059l-6.25 7a.75.75 0 0 1-1.114-.006L.66 4.906a.75.75 0 1 1 1.134-.984l2.543 2.93 5.675-6.252a.75.75 0 0 1 1.059-.047zM15 1.5l-6 6.75-1.5-1.5 6-6.75L15 1.5z"/>
                </svg>
              </span>
              {{ chat.last_message_preview || 'No messages' }}
            </p>
            <span
              v-if="chat.unread_count > 0"
              class="shrink-0 bg-green-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-medium"
            >
              {{ chat.unread_count > 99 ? '99+' : chat.unread_count }}
            </span>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>
