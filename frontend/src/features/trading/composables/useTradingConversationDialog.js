import { ref } from 'vue'
import { useRouter } from 'vue-router'

export function useTradingConversationDialog(conversationsStore) {
  const router = useRouter()
  const open = ref(false)
  const loading = ref(false)
  const error = ref('')
  const draft = ref('')
  const inquiry = ref(null)
  const title = ref('WA ChatLens')

  function begin(target, options) {
    open.value = true
    loading.value = true
    error.value = ''
    draft.value = options.draft
    inquiry.value = target
    title.value = options.title
  }

  async function openDirect(target, options) {
    if (!target?.account || !target?.contact) return
    begin(target, options)
    try {
      if (!conversationsStore.accounts.length) await conversationsStore.fetchChatsInitial()
      await conversationsStore.selectDirectChat(target.account, target.contact)
    } catch (requestError) {
      error.value = requestError.response?.data?.detail
        || requestError.message
        || 'Unable to open this direct conversation.'
    } finally {
      loading.value = false
    }
  }

  async function openSource(target, options) {
    if (!target?.source_chat_id) return
    begin(target, options)
    try {
      if (!conversationsStore.accounts.length) await conversationsStore.fetchChatsInitial()
      if (String(conversationsStore.selectedAccountId) !== String(target.account)) {
        await conversationsStore.switchAccount(target.account)
      } else if (!conversationsStore.chats.length) {
        await conversationsStore.fetchChats(target.account)
      }
      await conversationsStore.selectChat(target.source_chat_id, {
        messageId: target.source_message_id,
        messageTime: target.source_message_time,
      })
    } catch (requestError) {
      error.value = requestError.response?.data?.detail
        || requestError.message
        || 'Unable to open this conversation.'
    } finally {
      loading.value = false
    }
  }

  // Same deep link as openSource, but in the full WhatsApp Inbox page instead of the
  // modal. The store selection (chat + source message) carries over to the Inbox's
  // MessagePanel, which jumps to and marks the message.
  async function openSourceInInbox(target) {
    if (!target?.source_chat_id) return
    if (String(conversationsStore.selectedAccountId) !== String(target.account)) {
      await conversationsStore.switchAccount(target.account)
    }
    await router.push({ name: 'conversations' })
    await conversationsStore.selectChat(target.source_chat_id, {
      messageId: target.source_message_id,
      messageTime: target.source_message_time,
    })
  }

  function close() {
    open.value = false
    inquiry.value = null
    draft.value = ''
    error.value = ''
    title.value = 'WA ChatLens'
    conversationsStore.stopPolling()
  }

  return { open, loading, error, draft, inquiry, title, openDirect, openSource, openSourceInInbox, close }
}
