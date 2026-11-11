import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api', () => ({
  accountsApi: { list: vi.fn(), preflightMessage: vi.fn() },
  chatsApi: { messages: vi.fn(), markRead: vi.fn() },
  outboundAssetsApi: {},
}))

import MessagePanel from '../MessagePanel.vue'
import { useConversationsStore } from '@/stores/conversations'

const messagesFor = (ids) => ids.map(id => ({
  id, direction: 'inbound', message_time: '2026-11-11T10:00:00Z', message_text: `m${id}`,
}))

describe('MessagePanel deep link', () => {
  it('keeps the source message in view when it loads into an already-open panel', async () => {
    setActivePinia(createPinia())
    const store = useConversationsStore()
    store.chats = [{ id: 1 }, { id: 5 }]
    store.selectedChatId = 1
    store.messages = messagesFor([100, 101])

    const wrapper = mount(MessagePanel, {
      attachTo: document.body,
      global: { stubs: { ClientPulseChatAction: true } },
    })
    await flushPromises()
    const list = wrapper.find('.message-panel__messages').element
    let scrollTop = 0
    Object.defineProperty(list, 'scrollHeight', { configurable: true, get: () => 5000 })
    Object.defineProperty(list, 'scrollTop', { configurable: true, get: () => scrollTop, set: v => { scrollTop = v } })
    Object.defineProperty(list, 'clientHeight', { configurable: true, get: () => 500 })
    // jsdom has no layout: place the source message 1200px down the scrollable content.
    const rect = Element.prototype.getBoundingClientRect
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function () {
      if (this.dataset?.msgId === '2') return { top: 1200 - scrollTop, height: 0 }
      if (this === list) return { top: 0, height: 500 }
      return rect.call(this)
    })

    // What selectChat does for a deep link (Inbox page: the panel is already mounted).
    store.selectedChatId = 5
    store.highlightMessageId = null
    store.messages = []
    store.loadingMessages = true
    await flushPromises()
    store.messages = messagesFor([1, 2, 3, 4])
    store.highlightMessageId = 2
    store.loadingMessages = false
    await flushPromises()
    await new Promise(resolve => setTimeout(resolve, 200))

    // Centred: 1200 - (500 - 0) / 2. "Scroll to newest" would have left it at 5000.
    expect(scrollTop).toBe(950)
    expect(wrapper.find('[data-msg-id="2"]').classes()).toContain('msg-source')
    wrapper.unmount()
  })
})
