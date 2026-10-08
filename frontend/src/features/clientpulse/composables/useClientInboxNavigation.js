import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'

export function useClientInboxNavigation() {
  const router = useRouter()
  const conversations = useConversationsStore()
  const openingContactId = ref(null)

  async function openClientInbox(accountId, contactId) {
    openingContactId.value = contactId
    try {
      if (!conversations.accounts.length) await conversations.fetchChatsInitial()
      await conversations.selectDirectChat(accountId, contactId)
      await router.push({ name: 'conversations' })
    } finally {
      openingContactId.value = null
    }
  }

  return { openingContactId, openClientInbox }
}
