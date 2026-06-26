<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import ChatList from '@/components/ChatList.vue'
import MessagePanel from '@/components/MessagePanel.vue'

const store = useConversationsStore()

onMounted(async () => {
  await store.fetchChatsInitial()
  store.startPolling()
})

onUnmounted(() => store.stopPolling())
</script>

<template>
  <div class="flex h-full overflow-hidden">
    <ChatList class="w-80 shrink-0 h-full" />
    <MessagePanel class="flex-1 min-w-0 h-full" />
  </div>
</template>
