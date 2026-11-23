import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'

const route = vi.hoisted(() => ({ query: {} }))
const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(() => Promise.resolve()) }))
const api = vi.hoisted(() => ({
  opportunities: vi.fn(),
  getCardFieldConfig: vi.fn(() => Promise.resolve({ data: { fields: [] } })),
  getCardActionConfig: vi.fn(() => Promise.resolve({ data: { statuses: [], max_inline: 2 } })),
}))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => router }))
vi.mock('@/api', () => ({ realEstateApi: api }))
vi.mock('@/features/realEstate/composables/useOpportunityWhatsApp', async () => {
  const { ref } = await import('vue')
  return {
    useOpportunityWhatsApp: () => ({
      dialog: { open: ref(false), loading: ref(false), error: ref(''), draft: ref(''), inquiry: ref(null), title: ref(''), close: vi.fn() },
      viewSource: vi.fn(), openInInbox: vi.fn(), messageContact: vi.fn(),
    }),
  }
})

const buyer = { id: 25, activity_type: 'buying', status: 'new', summary: 'Needs a flat' }

async function mountBoard() {
  const { default: Board } = await import('@/views/RealEstateBoardView.vue')
  const wrapper = mount(Board, { attachTo: document.body, global: { stubs: { TradingConversationDialog: true } } })
  await flushPromises()
  return wrapper
}

describe('Opportunity Board and its matches', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    useAuthStore().user = { current_company: { id: 3 }, permissions: { 'real_estate.opportunities.view': 'all' } }
    api.opportunities.mockImplementation(params => Promise.resolve({
      data: { count: 30, results: params.activity_type === 'buying' ? [buyer] : [] },
    }))
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('remembers its lane, page, filters and the card before opening the matches', async () => {
    route.query = { lane: 'buying', page: '2', status: 'new', search: 'flat' }
    const wrapper = await mountBoard()
    await wrapper.findAll('button').find(b => b.text() === 'Find sellers').trigger('click')
    await flushPromises()

    expect(router.replace).toHaveBeenCalledWith({
      name: 'real-estate-board',
      query: { lane: 'buying', page: '2', status: 'new', search: 'flat', focus: '25' },
    })
    expect(router.push).toHaveBeenCalledWith({ name: 'real-estate-search', query: { counterparts: 25 } })
    wrapper.unmount()
  })

  it('comes back on the same page with the same filters and highlights the card', async () => {
    route.query = { lane: 'buying', page: '2', status: 'new', search: 'flat', focus: '25' }
    const wrapper = await mountBoard()

    const buyingCall = api.opportunities.mock.calls.find(([params]) => params.activity_type === 'buying')[0]
    expect(buyingCall).toMatchObject({ page: 2, status: 'new', search: 'flat' })
    const card = wrapper.find('[data-opportunity-id="25"]')
    expect(card.classes()).toContain('is-focused')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    wrapper.unmount()
  })
})
