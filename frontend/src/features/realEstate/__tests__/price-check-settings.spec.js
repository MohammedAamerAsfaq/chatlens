import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PriceCheckSettings from '../components/PriceCheckSettings.vue'

const api = vi.hoisted(() => ({
  getPriceCheck: vi.fn(), setPriceCheck: vi.fn(), marketPrices: vi.fn(), propertyTypes: vi.fn(),
  createMarketPrice: vi.fn(), updateMarketPrice: vi.fn(), deleteMarketPrice: vi.fn(),
}))
vi.mock('@/api', () => ({ realEstateApi: api }))

const choices = [
  { value: 'off', label: 'Off' },
  { value: 'model_knowledge', label: "AI's own market knowledge" },
  { value: 'web_search', label: 'Live web search (OpenRouter)' },
  { value: 'reference_table', label: 'Company price table' },
]
const check = (overrides = {}) => ({ mode: 'model_knowledge', choices, web_search_blockers: [], table_rows: 0, ...overrides })

describe('PriceCheckSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getPriceCheck.mockResolvedValue({ data: check() })
    api.marketPrices.mockResolvedValue({ data: [] })
    api.propertyTypes.mockResolvedValue({ data: [{ id: 14, name: 'Apartment' }] })
  })

  it('shows the four choices and saves the chosen one', async () => {
    api.setPriceCheck.mockResolvedValue({ data: check({ mode: 'off' }) })
    const wrapper = mount(PriceCheckSettings)
    await flushPromises()
    expect(wrapper.findAll('input[type="radio"]')).toHaveLength(4)
    expect(wrapper.find('input[value="model_knowledge"]').element.checked).toBe(true)
    expect(wrapper.text()).toContain('Rent paid in cheques')

    await wrapper.find('input[value="off"]').setValue(true)
    await wrapper.findAll('button').find(b => b.text() === 'Save price check').trigger('click')
    await flushPromises()
    expect(api.setPriceCheck).toHaveBeenCalledWith('off')
    expect(wrapper.text()).toContain('Saved.')
  })

  it('explains why web search is not available and shows the server refusal', async () => {
    api.getPriceCheck.mockResolvedValue({ data: check({ web_search_blockers: ['DeepSeek (deepseek)'] }) })
    api.setPriceCheck.mockRejectedValue({ response: { status: 400, data: { mode: ['Web search needs OpenRouter models'] } } })
    const wrapper = mount(PriceCheckSettings)
    await flushPromises()
    expect(wrapper.text()).toContain('Not available yet: the extraction AI uses DeepSeek (deepseek).')
    await wrapper.find('input[value="web_search"]').setValue(true)
    await wrapper.findAll('button').find(b => b.text() === 'Save price check').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('Web search needs OpenRouter models')
  })

  it('adds a price to the company table', async () => {
    api.createMarketPrice.mockImplementation(data => Promise.resolve({ data: { id: 1, property_type_name: 'Apartment', ...data } }))
    const wrapper = mount(PriceCheckSettings)
    await flushPromises()
    await wrapper.find('input[aria-label="New area"]').setValue('Dubai Marina')
    await wrapper.find('select[aria-label="New property type"]').setValue(14)
    await wrapper.find('input[aria-label="New bedrooms"]').setValue(2)
    await wrapper.find('input[aria-label="New sale price from"]').setValue(1800000)
    await wrapper.find('input[aria-label="New sale price to"]').setValue(2600000)
    await wrapper.findAll('button').find(b => b.text() === 'Add price').trigger('click')
    await flushPromises()

    expect(api.createMarketPrice).toHaveBeenCalledWith({
      location: 'Dubai Marina', property_type: 14, bedrooms: 2,
      sale_price_min: 1800000, sale_price_max: 2600000, currency: 'AED', notes: '',
    })
    expect(wrapper.text()).toContain('AED 1,800,000 to 2,600,000')
    expect(wrapper.text()).toContain('1 price in the table.')
    expect(wrapper.find('input[aria-label="New area"]').element.value).toBe('')
  })

  it('warns before removing the last price while the table is in use', async () => {
    api.getPriceCheck.mockResolvedValue({ data: check({ mode: 'reference_table', table_rows: 1 }) })
    api.marketPrices.mockResolvedValue({ data: [{ id: 1, location: 'JVC', property_type_name: '', bedrooms: null, sale_price_min: '500000', sale_price_max: '800000', currency: 'AED', notes: '' }] })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = mount(PriceCheckSettings)
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Remove').trigger('click')
    expect(confirm.mock.calls[0][0]).toContain('new messages will fail to process')
    expect(api.deleteMarketPrice).not.toHaveBeenCalled()
    confirm.mockRestore()
  })
})
