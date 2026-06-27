<script setup>
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'

const route = useRoute()
const store = useConversationsStore()
</script>

<template>
  <div class="h-screen bg-gray-50 flex flex-col overflow-hidden">
    <nav class="bg-gray-900 text-white px-6 py-3 flex items-center gap-6 shadow shrink-0">
      <span class="text-green-400 font-bold text-lg mr-4">ChatLens</span>
      <RouterLink
        to="/"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Sessions
      </RouterLink>
      <RouterLink
        to="/conversations"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Conversations
      </RouterLink>
      <RouterLink
        to="/activity"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Activity
      </RouterLink>
      <RouterLink
        to="/storage"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Storage
      </RouterLink>
      <RouterLink
        to="/message-logs"
        class="text-sm text-gray-300 hover:text-white transition-colors"
        active-class="text-white font-medium"
      >
        Message Logs
      </RouterLink>

      <!-- Account switcher — shown in nav when on Conversations page -->
      <div
        v-if="route.name === 'conversations' && store.accounts.length"
        class="ml-auto flex items-center gap-1"
      >
        <button
          v-for="account in store.accounts"
          :key="account.id"
          @click="store.switchAccount(account.id)"
          :class="[
            'relative flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
            store.selectedAccountId === account.id
              ? 'bg-green-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white',
          ]"
        >
          <span
            :class="['w-1.5 h-1.5 rounded-full shrink-0', account.session_status === 'connected' ? 'bg-green-300' : 'bg-gray-500']"
          />
          {{ account.display_name || account.phone_number || `Account #${account.id}` }}
          <!-- Unread badge -->
          <span
            v-if="account.total_unread > 0"
            class="ml-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1 leading-none"
          >
            {{ account.total_unread > 99 ? '99+' : account.total_unread }}
          </span>
        </button>
      </div>
    </nav>
    <div class="flex-1 flex flex-col overflow-hidden min-h-0">
      <RouterView class="h-full" />
    </div>
  </div>
</template>
