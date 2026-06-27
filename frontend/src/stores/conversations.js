import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatsApi, accountsApi } from '@/api'

function clearUnread(chats, accounts, chatId, accountId) {
  const chat = chats.find(c => c.id === chatId)
  if (!chat || !chat.unread_count) return
  chat.unread_count = 0
  // total_unread counts chats-with-unread, so decrement by 1 per chat cleared
  const account = accounts?.find(a => a.id === accountId)
  if (account) account.total_unread = Math.max(0, (account.total_unread || 0) - 1)
}

export const useConversationsStore = defineStore('conversations', () => {
  const chats = ref([])
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const selectedChatId = ref(null)
  const messages = ref([])
  const loadingChats = ref(false)
  const loadingMessages = ref(false)
  const loadingOlderMessages = ref(false)
  const hasMoreMessages = ref(false)
  const searchQuery = ref('')

  let chatPollTimer = null
  let messagePollTimer = null

  const selectedChat = computed(() => chats.value.find(c => c.id === selectedChatId.value))
  const selectedAccount = computed(() => accounts.value.find(a => a.id === selectedAccountId.value))

  const filteredChats = computed(() => {
    if (!searchQuery.value) return chats.value
    const q = searchQuery.value.toLowerCase()
    return chats.value.filter(c =>
      c.display_name?.toLowerCase().includes(q) ||
      c.wa_chat_id?.toLowerCase().includes(q)
    )
  })

  async function fetchAccounts() {
    try {
      const { data } = await accountsApi.list()
      accounts.value = data.filter(a => a.session_status === 'connected' || a.phone_number)
      if (accounts.value.length && !selectedAccountId.value) {
        selectedAccountId.value = accounts.value[0].id
      }
    } catch {}
  }

  async function switchAccount(accountId) {
    selectedAccountId.value = accountId
    selectedChatId.value = null
    messages.value = []
    searchQuery.value = ''
    await fetchChats(accountId)
  }

  async function fetchChats(accountId = null) {
    const id = accountId ?? selectedAccountId.value
    const params = id ? { account: id } : {}
    try {
      const { data } = await chatsApi.list(params)
      chats.value = data
      // Keep the open chat's badge cleared in the refreshed list
      if (selectedChatId.value) {
        clearUnread(chats.value, accounts.value, selectedChatId.value, id)
      }
    } catch {}
  }

  async function fetchChatsInitial() {
    loadingChats.value = true
    await fetchAccounts()
    await fetchChats(selectedAccountId.value)
    loadingChats.value = false
  }

  async function refreshMessages(chatId) {
    if (selectedChatId.value !== chatId) return
    if (!messages.value.length) return
    try {
      const newest = messages.value[messages.value.length - 1]
      const { data } = await chatsApi.messages(chatId, { after: newest.message_time, limit: 20 })
      if (data.results.length) {
        const existingIds = new Set(messages.value.map(m => m.id))
        const fresh = data.results.filter(m => !existingIds.has(m.id))
        if (fresh.length) messages.value = [...messages.value, ...fresh]
      }
    } catch {}
  }

  async function loadOlderMessages() {
    if (!selectedChatId.value || loadingOlderMessages.value || !hasMoreMessages.value) return
    if (!messages.value.length) return
    loadingOlderMessages.value = true
    try {
      const oldest = messages.value[0]
      const { data } = await chatsApi.messages(selectedChatId.value, {
        before: oldest.message_time,
        limit: 40,
      })
      messages.value = [...data.results, ...messages.value]
      hasMoreMessages.value = data.has_more
    } catch {}
    finally { loadingOlderMessages.value = false }
  }

  async function selectChat(id) {
    selectedChatId.value = id
    messages.value = []
    hasMoreMessages.value = false
    loadingMessages.value = true
    clearInterval(messagePollTimer)
    clearUnread(chats.value, accounts.value, id, selectedAccountId.value)
    // Fire markRead independently — don't let its failure block message loading
    chatsApi.markRead(id).catch(() => {})
    try {
      const { data } = await chatsApi.messages(id, { limit: 40 })
      messages.value = data.results
      hasMoreMessages.value = data.has_more
    } finally {
      loadingMessages.value = false
    }
    messagePollTimer = setInterval(() => refreshMessages(id), 5000)
  }

  async function markAllRead() {
    await chatsApi.markAllRead(selectedAccountId.value).catch(() => {})
    // Zero all badge counts locally so the UI updates instantly
    chats.value.forEach(c => { c.unread_count = 0 })
    const account = accounts.value.find(a => a.id === selectedAccountId.value)
    if (account) account.total_unread = 0
  }

  function startPolling() {
    chatPollTimer = setInterval(async () => {
      await fetchChats(selectedAccountId.value)
      // Refresh all accounts so total_unread stays accurate for non-selected accounts
      fetchAccounts()
    }, 8000)
  }

  function stopPolling() {
    clearInterval(chatPollTimer)
    clearInterval(messagePollTimer)
  }

  return {
    chats, accounts, selectedAccountId, selectedAccount,
    selectedChatId, messages, loadingChats, loadingMessages,
    loadingOlderMessages, hasMoreMessages,
    searchQuery, selectedChat, filteredChats,
    fetchChats, fetchChatsInitial, selectChat, switchAccount,
    loadOlderMessages, markAllRead, startPolling, stopPolling,
  }
})
