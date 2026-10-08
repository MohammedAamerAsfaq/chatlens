import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProductPriceUpdateView from '../ProductPriceUpdateView.vue'

const api = vi.hoisted(() => ({
  listAutomationRules: vi.fn(),
  captureSummary: vi.fn(),
  listPriceCaptures: vi.fn(),
}))

vi.mock('@/api/index.js', () => ({
  tradingApi: api,
  contactsApi: {},
  groupsApi: {},
  accountsApi: { list: vi.fn().mockResolvedValue({ data: [] }) },
}))

describe('price automation records', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listAutomationRules.mockResolvedValue({
      data: [{
        id: 6,
        name: 'Update Qty and Cost',
        update_type: 'qty_cost',
        is_active: true,
        sources: [],
        trigger_heading: '',
        trigger_ai_detect: false,
        action_mode: 'auto',
        zero_unmatched_qty: true,
        regenerate_price_list: false,
        last_triggered_at: null,
        trigger_count: 0,
      }],
    })
    api.listPriceCaptures.mockResolvedValue({ data: { results: [], count: 0 } })
  })

  it('keeps existing rules visible when the summary request fails', async () => {
    api.captureSummary.mockRejectedValue(new Error('summary unavailable'))

    const wrapper = mount(ProductPriceUpdateView, {
      props: { mode: 'automation' },
      global: {
        directives: { uiDataTable: {} },
        stubs: { RouterLink: { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Update Qty and Cost')
    expect(wrapper.text()).toContain('Automation summary could not be loaded.')
    expect(wrapper.text()).not.toContain('No automation rules yet.')
  })
})
