import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OpportunityCard from '../components/OpportunityCard.vue'

const route = vi.hoisted(() => ({ query: {} }))
const router = vi.hoisted(() => ({
  push: vi.fn(), replace: vi.fn(), back: vi.fn(),
  resolve: ({ name }) => ({ path: name === 'real-estate-board' ? '/real-estate' : '/real-estate/search' }),
}))
const api = vi.hoisted(() => ({ searchOpportunities: vi.fn(), opportunityCounterparts: vi.fn(), getOpportunity: vi.fn() }))
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

const lane = { key: 'buying', tone: 'buying' }
const card = activity => mount(OpportunityCard, { props: { opportunity: { id: 7, activity_type: activity, status: 'new' }, lane } })

describe('OpportunityCard counterpart action', () => {
  it.each([
    ['buying', 'Find sellers'],
    ['selling', 'Find buyers'],
    ['leasing_inquiry', 'Find landlords'],
    ['leasing_offer', 'Find tenants'],
  ])('a %s card offers "%s"', async (activity, label) => {
    const wrapper = card(activity)
    const button = wrapper.findAll('button').find(b => b.text() === label)
    expect(button).toBeTruthy()
    await button.trigger('click')
    expect(wrapper.emitted('find-counterparts')[0][0].id).toBe(7)
  })
})

describe('Opportunity Search counterpart mode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = { counterparts: '12' }
    api.getOpportunity.mockResolvedValue({ data: { id: 12, activity_type: 'buying', contact_name: 'Saidou', summary: 'Needs a 2 bed in Marina' } })
    api.opportunityCounterparts.mockResolvedValue({
      data: {
        count: 1,
        results: [{ id: 30, activity_type: 'selling', status: 'new', summary: 'Marina 2 bed for sale', items: [], search_score: 0.8, search_relevance: 'strong', search_reasons: ['location'] }],
        search_interpretation: { canonical_query: 'Apartment; Dubai Marina; 2 bedrooms' },
        search_corrections: [],
      },
    })
  })

  it('ranks the other side of the opportunity instead of running a typed search', async () => {
    const { default: View } = await import('@/views/RealEstateOpportunitySearchView.vue')
    const wrapper = mount(View, { global: { stubs: { TradingConversationDialog: true } } })
    await flushPromises()

    expect(api.searchOpportunities).not.toHaveBeenCalled()
    expect(api.opportunityCounterparts).toHaveBeenCalledWith(12, expect.objectContaining({ relevance: 'possible', page: 1 }))
    expect(wrapper.text()).toContain('Sellers for #12')
    expect(wrapper.text()).toContain('Matching on: Apartment; Dubai Marina; 2 bedrooms')
    expect(wrapper.text()).toContain('Marina 2 bed for sale')
    expect(wrapper.text()).toContain('80% strong')

  })

  it('goes back to the board card it came from', async () => {
    window.history.replaceState({ back: '/real-estate?lane=buying&page=2&focus=12' }, '')
    const { default: View } = await import('@/views/RealEstateOpportunitySearchView.vue')
    const wrapper = mount(View, { global: { stubs: { TradingConversationDialog: true } } })
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Back to board').trigger('click')
    expect(router.back).toHaveBeenCalled()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('opens the card on the board when it did not come from there', async () => {
    window.history.replaceState({ back: null }, '')
    const { default: View } = await import('@/views/RealEstateOpportunitySearchView.vue')
    const wrapper = mount(View, { global: { stubs: { TradingConversationDialog: true } } })
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Back to board').trigger('click')
    expect(router.back).not.toHaveBeenCalled()
    expect(router.push).toHaveBeenCalledWith({ name: 'real-estate-board', query: { lane: 'buying', focus: '12' } })
  })

  it('shows why a match could not be searched', async () => {
    api.opportunityCounterparts.mockRejectedValue({ response: { status: 400, data: { non_field_errors: 'This opportunity has no property details or message to match on.' } } })
    const { default: View } = await import('@/views/RealEstateOpportunitySearchView.vue')
    const wrapper = mount(View, { global: { stubs: { TradingConversationDialog: true } } })
    await flushPromises()
    expect(wrapper.text()).toContain('no property details or message to match on')
  })
})

describe('Opportunity Search progress', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = { counterparts: '12' }
    api.getOpportunity.mockResolvedValue({ data: { id: 12, activity_type: 'buying', contact_name: 'Saidou' } })
  })

  it('shows that the search is running until the results arrive', async () => {
    let finish
    api.opportunityCounterparts.mockReturnValue(new Promise(resolve => { finish = resolve }))
    const { default: View } = await import('@/views/RealEstateOpportunitySearchView.vue')
    const wrapper = mount(View, { global: { stubs: { TradingConversationDialog: true } } })
    await flushPromises()

    expect(wrapper.find('.opportunity-search__progress').text()).toContain('Finding sellers...')
    expect(wrapper.find('.ui-spinner').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('No opportunities match this search.')
    expect(wrapper.text()).not.toContain('0 opportunities')

    finish({ data: { count: 0, results: [], search_corrections: [] } })
    await flushPromises()
    expect(wrapper.find('.opportunity-search__progress').exists()).toBe(false)
    expect(wrapper.text()).toContain('No opportunities match this search.')
  })
})
