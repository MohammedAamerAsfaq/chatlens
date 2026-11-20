import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignSettingsView from '../CampaignSettingsView.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({ getCampaignCurrencySettings: vi.fn(), setCampaignCurrencySettings: vi.fn() }))
vi.mock('@/api', () => ({ tradingApi: api }))

const stored = () => ({
  primary: { code: 'AED', symbol: 'AED' }, label: 'code', label_position: 'prefix',
  decimals: 2, trim_zeros: true, separator: ' / ', others: [],
})

describe('CampaignSettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    useAuthStore().user = { current_company: { id: 1 }, permissions: { 'campaigns.campaigns.view': 'all', 'settings.company.manage': 'all' } }
    api.getCampaignCurrencySettings.mockResolvedValue({ data: stored() })
    api.setCampaignCurrencySettings.mockImplementation(data => Promise.resolve({ data }))
  })

  it('adds a converted currency and saves it', async () => {
    const wrapper = mount(CampaignSettingsView)
    await flushPromises()
    expect(wrapper.text()).toContain('AED 27')

    await wrapper.findAll('button').find(b => b.text() === '+ Add currency').trigger('click')
    await wrapper.find('input[aria-label="Currency 1 code"]').setValue('usd')
    await wrapper.find('input[aria-label="Currency 1 code"]').trigger('change')
    await wrapper.find('input[aria-label="Currency 1 rate"]').setValue('0.2723')
    expect(wrapper.find('input[aria-label="Currency 1 symbol"]').element.value).toBe('$')
    expect(wrapper.text()).toContain('AED 27 / USD 7.35')

    await wrapper.findAll('button').find(b => b.text() === 'Save currency settings').trigger('click')
    await flushPromises()
    const sent = api.setCampaignCurrencySettings.mock.calls[0][0]
    expect(sent.others[0]).toMatchObject({ code: 'USD', symbol: '$', rate: 0.2723, enabled: true })
    expect(wrapper.text()).toContain('Currency settings saved')
  })

  it('shows the server reason when a setting is invalid', async () => {
    api.setCampaignCurrencySettings.mockRejectedValue({ response: { data: { 'others.0.rate': ['Enter how much USD one AED buys (more than 0).'] } } })
    const wrapper = mount(CampaignSettingsView)
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Save currency settings').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Enter how much USD one AED buys')
  })

  it('is read-only for members who are not company admins', async () => {
    useAuthStore().user.permissions = { 'campaigns.campaigns.view': 'all' }
    const wrapper = mount(CampaignSettingsView)
    await flushPromises()
    expect(wrapper.find('fieldset').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('button').some(b => b.text() === 'Save currency settings')).toBe(false)
  })
})
