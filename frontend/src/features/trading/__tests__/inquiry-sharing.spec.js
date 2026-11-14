import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import InquiryCardActions from '../components/InquiryCardActions.vue'
import InquiryCardHeader from '../components/InquiryCardHeader.vue'
import InquiryStockHints from '../components/InquiryStockHints.vue'
import { useTradingConversationDialog } from '../composables/useTradingConversationDialog'

const sharedDirectChat = vi.fn()
vi.mock('@/api', () => ({ tradingApi: { sharedDirectChat: (...args) => sharedDirectChat(...args) } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const own = {
  id: 1, inquiry_type: 'buy', contact: 7, source_chat_id: 9, products: [{ id: 1 }], status: 'open',
  is_shared: false, shared_by: [],
  shared_handling: [{ user_id: 3, user_name: 'Bob', status: 'quoted_waiting', status_label: 'Quoted - Waiting', remarks: '', updated_at: '2026-11-14T10:05:00Z' }],
}
const shared = {
  id: 2, inquiry_type: 'buy', contact: 7, source_chat_id: null, products: [{ id: 1 }], status: 'quoted_waiting',
  is_shared: true, shared_by: ['Aamer'], shared_handling: [],
}

describe('Inquiry sharing on cards', () => {
  it('shows a share button and who handled an own inquiry', async () => {
    const wrapper = mount(InquiryCardHeader, { props: { inquiry: own, canShare: true } })
    expect(wrapper.find('.handled-by').text()).toContain('Bob · Quoted - Waiting')
    expect(wrapper.find('.category-select').exists()).toBe(true)
    await wrapper.find('.share').trigger('click')
    expect(wrapper.emitted('share')).toHaveLength(1)
  })

  it('marks a shared inquiry and hides owner-only controls', () => {
    const header = mount(InquiryCardHeader, { props: { inquiry: shared, canShare: true } })
    expect(header.find('.shared-by').text()).toBe('Shared by Aamer')
    expect(header.find('.own-status').text()).toBe('Quoted - Waiting')
    expect(header.find('.share').exists()).toBe(false)
    expect(header.find('.category-select').exists()).toBe(false)

    const actions = mount(InquiryCardActions, { props: { inquiry: shared, manualMatchAvailable: true } })
    expect(actions.find('.products-menu').exists()).toBe(false)
    expect(actions.find('.market').exists()).toBe(false)
    expect(actions.text()).not.toContain('WA ChatLens')
    expect(actions.text()).toContain('ChatLens')

    const hint = { index: 0, name: 'x', product: { name: 'iPhone', qty: 1 }, mismatch: true }
    expect(mount(InquiryStockHints, { props: { hints: [hint], readOnly: true } }).find('.actions').exists()).toBe(false)
    expect(mount(InquiryStockHints, { props: { hints: [hint] } }).find('.actions').exists()).toBe(true)
  })

  it('opens a shared inquiry direct chat on the viewer own account', async () => {
    sharedDirectChat.mockResolvedValue({ data: { id: 55 } })
    const store = {
      accounts: [{ id: 4 }],
      selectResolvedChat: vi.fn(async (accountId, resolve) => resolve()),
    }
    const dialog = useTradingConversationDialog(store)
    await dialog.openSharedDirect(shared, 4, { title: 'Direct', draft: 'WTS' })

    expect(store.selectResolvedChat).toHaveBeenCalledWith(4, expect.any(Function))
    expect(sharedDirectChat).toHaveBeenCalledWith(2, 4)
    expect(dialog.error.value).toBe('')
    expect(dialog.draft.value).toBe('WTS')
  })

  it('fails loudly when the viewer has no account to message from', async () => {
    const store = { accounts: [], selectResolvedChat: vi.fn() }
    const dialog = useTradingConversationDialog(store)
    await dialog.openSharedDirect(shared, null, { title: 'Direct', draft: '' })
    expect(store.selectResolvedChat).not.toHaveBeenCalled()
    expect(dialog.error.value).toContain('WhatsApp account of your own')
  })
})
