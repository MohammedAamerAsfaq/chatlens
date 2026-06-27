<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import ChatList from '@/components/ChatList.vue'
import MessagePanel from '@/components/MessagePanel.vue'
import ChatInfoPanel from '@/components/ChatInfoPanel.vue'

const store   = useConversationsStore()
const showInfo = ref(false)

function toggleInfo() { showInfo.value = !showInfo.value }
function closeInfo()  { showInfo.value = false }

// Close info panel when chat changes
import { watch } from 'vue'
watch(() => store.selectedChatId, () => { showInfo.value = false })

onMounted(async () => {
  await store.fetchChatsInitial()
  store.startPolling()
})
onUnmounted(() => store.stopPolling())
</script>

<template>
  <div class="flex h-full overflow-hidden">
    <ChatList class="w-80 shrink-0 h-full" />
    <MessagePanel class="flex-1 min-w-0 h-full" @toggle-info="toggleInfo" />

    <!-- Sliding info panel — width transitions from 0 → 320px -->
    <div
      :class="['h-full overflow-hidden shrink-0 transition-all duration-300', showInfo ? 'w-80' : 'w-0']"
    >
      <ChatInfoPanel :open="showInfo" @close="closeInfo" />
    </div>
  </div>
</template>
