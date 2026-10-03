import { nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useDraggableDialog } from '../composables/useDraggableDialog'
import { useInquiryMatchController } from '../composables/useInquiryMatchController'
import { useInquiryProductsController } from '../composables/useInquiryProductsController'
import { useMarketPartiesController } from '../composables/useMarketPartiesController'
import { useTradingContactPicker } from '../composables/useTradingContactPicker'
import { useTradingConversationDialog } from '../composables/useTradingConversationDialog'
import { feedDateRangeParams, useTradingFeedController } from '../composables/useTradingFeedController'

describe('Trading feature controllers', () => {
  it('builds local calendar and rolling feed ranges', () => {
    const now = new Date('2026-10-03T12:00:00+04:00')
    const rolling = feedDateRangeParams('last_hour', now)
    expect(new Date(rolling.date_from).getTime()).toBe(now.getTime() - 60 * 60 * 1000)
    expect(rolling.date_to).toBe(now.toISOString())

    const yesterday = feedDateRangeParams('yesterday', now)
    expect(new Date(yesterday.date_from).getHours()).toBe(0)
    expect(new Date(yesterday.date_to).getTime() - new Date(yesterday.date_from).getTime()).toBe(24 * 60 * 60 * 1000)
  })

  it('loads and paginates independent buy and sell feeds', async () => {
    const api = {
      getStats: vi.fn().mockResolvedValue({ data: { today: {} } }),
      getOpenFeed: vi.fn(({ type, page }) => Promise.resolve({ data: { results: [`${type}-${page}`], count: 120 } })),
      listProducts: vi.fn().mockResolvedValue({ data: { results: [{ id: 7 }] } }),
    }
    const controller = useTradingFeedController({
      api,
      accountId: ref(3),
      status: ref('open'),
      contacts: { buy: ref(''), sell: ref('') },
      resetContact: vi.fn(),
    })

    await controller.refresh()
    expect(controller.buy.items.value).toEqual(['buy-1'])
    expect(controller.sell.items.value).toEqual(['sell-1'])
    expect(controller.products.value).toEqual([{ id: 7 }])

    await controller.changePage('buy', 2)
    expect(controller.buy.items.value).toEqual(['buy-2'])
    expect(controller.sell.page.value).toBe(1)
  })

  it('loads and selects contacts through the picker controller', async () => {
    const changed = vi.fn()
    const picker = useTradingContactPicker({
      accountId: ref(4),
      listContacts: vi.fn().mockResolvedValue({ data: { results: [{ id: 9, display_name: 'Supplier' }], count: 1 } }),
      onSelectionChange: changed,
    })

    await picker.load('buy', { reset: true })
    picker.select('buy', picker.buy.options.value[0])
    expect(picker.buy.selected.value).toBe(9)
    expect(picker.buy.search.value).toBe('Supplier')
    expect(changed).toHaveBeenCalledWith('buy')
    picker.destroy()
  })

  it('tracks and resets dialog drag offsets', async () => {
    const drag = useDraggableDialog()
    drag.start(new MouseEvent('mousedown', { clientX: 10, clientY: 20 }))
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 35, clientY: 60 }))
    await nextTick()
    expect(drag.position.value).toEqual({ x: 25, y: 40 })
    drag.stop()
    drag.reset()
    expect(drag.position.value).toEqual({ x: 0, y: 0 })
  })

  it('prefers direct product aliases before embedding search', async () => {
    const api = { searchProductEmbeddings: vi.fn(), correctMatch: vi.fn() }
    const controller = useInquiryMatchController({
      api,
      products: ref([{ id: 4, name: 'iPhone 18 Pro', aliases: ['18 pro'] }]),
      buildLines: vi.fn(),
    })

    await controller.autoMatch({ id: 10 }, { index: 0, name: '18 pro' })
    expect(controller.results.value[0]).toMatchObject({ source: 'direct', product: { id: 4 } })
    expect(api.searchProductEmbeddings).not.toHaveBeenCalled()
  })

  it('opens source conversations after switching account', async () => {
    const store = {
      accounts: [{}],
      chats: [],
      selectedAccountId: 1,
      switchAccount: vi.fn().mockResolvedValue(),
      selectChat: vi.fn().mockResolvedValue(),
      stopPolling: vi.fn(),
    }
    const dialog = useTradingConversationDialog(store)
    await dialog.openSource(
      { account: 2, source_chat_id: 8, source_message_id: 12, source_message_time: 'now' },
      { title: 'Reference', draft: 'Text' },
    )

    expect(store.switchAccount).toHaveBeenCalledWith(2)
    expect(store.selectChat).toHaveBeenCalledWith(8, { messageId: 12, messageTime: 'now' })
    expect(dialog.loading.value).toBe(false)
    expect(dialog.error.value).toBe('')
  })

  it('creates a catalog product and patches the inquiry feed', async () => {
    const patchInquiry = vi.fn()
    const products = ref([])
    const api = {
      getInquiryProductLines: vi.fn().mockResolvedValue({ data: { products: [{ index: 0 }] } }),
      createProductFromInquiryLine: vi.fn().mockResolvedValue({
        data: { product: { id: 6, name: 'LCD A15' }, inquiry: { id: 11, products: [] } },
      }),
      trackNonInventoryFromInquiryLine: vi.fn(),
    }
    const controller = useInquiryProductsController({ api, products, patchInquiry })
    await controller.show({ id: 11 })
    await controller.createProduct({ index: 0, brand: 'Samsung' })

    expect(products.value).toEqual([{ id: 6, name: 'LCD A15' }])
    expect(patchInquiry).toHaveBeenCalledWith({ id: 11, products: [] })
    expect(controller.creatingIndex.value).toBeNull()
  })

  it('reloads market parties when the source changes', async () => {
    const api = {
      getInquiryMarketParties: vi.fn().mockResolvedValue({
        data: { inquiry: { id: 12, inquiry_type: 'sell' }, products: [{ id: 3 }], source: 'inventory', method: 'exact' },
      }),
    }
    const controller = useMarketPartiesController(api)
    await controller.show({ id: 12, inquiry_type: 'sell' })
    expect(controller.title.value).toBe('Potential Buyers')
    expect(controller.products.value).toEqual([{ id: 3 }])

    api.getInquiryMarketParties.mockResolvedValueOnce({ data: { products: [], source: 'market', method: 'exact' } })
    await controller.setSource('market')
    expect(api.getInquiryMarketParties).toHaveBeenLastCalledWith(12, {
      limit: 25,
      market_source: 'market',
      market_method: 'exact',
    })
  })
})
