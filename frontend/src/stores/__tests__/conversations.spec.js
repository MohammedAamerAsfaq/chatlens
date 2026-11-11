import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api', () => ({
  accountsApi: { list: vi.fn() },
  chatsApi: { messages: vi.fn(), markRead: vi.fn().mockResolvedValue() },
}))

import { chatsApi } from '@/api'
import { useConversationsStore } from '../conversations'

describe('conversations store deep links', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    chatsApi.messages.mockReset()
  })

  it('loads messages on both sides of the source message', async () => {
    chatsApi.messages.mockImplementation((_chatId, params) => Promise.resolve({
      data: params.before
        ? { results: [{ id: 1 }, { id: 2 }], has_more: true }
        : { results: [{ id: 2 }, { id: 3 }], has_more: false },
    }))
    const store = useConversationsStore()
    await store.selectChat(5, { messageId: 2, messageTime: '2026-11-11T10:00:00Z' })

    expect(chatsApi.messages).toHaveBeenCalledWith(5, { before: '2026-11-11T10:00:01.000Z', limit: 30 })
    expect(chatsApi.messages).toHaveBeenCalledWith(5, { after: '2026-11-11T10:00:01.000Z', limit: 20 })
    expect(store.messages.map(m => m.id)).toEqual([1, 2, 3])
    expect(store.hasMoreMessages).toBe(true)
    expect(store.highlightMessageId).toBe(2)
    store.stopPolling()
  })
})
