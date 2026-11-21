import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignCurrencyBar from '../components/CampaignCurrencyBar.vue'
import { useAuthStore } from '@/stores/auth'

const company = () => ({
  primary: { code: 'AED', symbol: 'AED' }, label: 'code', label_position: 'prefix',
  decimals: 2, trim_zeros: true, separator: ' / ',
  others: [{ code: 'USD', symbol: '$', rate: 0.2723, enabled: true }],
})

function mountBar(props = {}) {
  const save = props.save || vi.fn(settings => Promise.resolve({ data: { id: 5, currency_settings: settings } }))
  const wrapper = mount(CampaignCurrencyBar, { props: { campaign: { id: 5, currency_settings: null }, company: company(), save, ...props } })
  return { wrapper, save }
}

describe('CampaignCurrencyBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().user = { current_company: { id: 1 }, permissions: { 'campaigns.campaigns.update': 'all' } }
  })

  it('follows the company settings by default', () => {
    const { wrapper } = mountBar()
    expect(wrapper.find('.currency-bar__switch .active').text()).toBe('Company default')
    expect(wrapper.text()).toContain('AED 27 / USD 7.35')
    expect(wrapper.find('select[aria-label="Number of currencies"]').element.value).toBe('multiple')
  })

  it('switching to one currency gives the campaign its own settings', async () => {
    const { wrapper, save } = mountBar()
    await wrapper.find('select[aria-label="Number of currencies"]').setValue('one')
    await flushPromises()
    const sent = save.mock.calls[0][0]
    expect(sent.others[0]).toMatchObject({ code: 'USD', enabled: false })
    expect(wrapper.emitted('saved')[0][0].id).toBe(5)
  })

  it('hides or shows the currency label', async () => {
    const { wrapper, save } = mountBar()
    await wrapper.find('select[aria-label="Show currency as"]').setValue('none')
    await flushPromises()
    expect(save.mock.calls[0][0].label).toBe('none')
  })

  it('goes back to the company default by clearing its own settings', async () => {
    const own = { ...company(), label: 'symbol', others: [] }
    const { wrapper, save } = mountBar({ campaign: { id: 5, currency_settings: own } })
    expect(wrapper.text()).toContain('AED 27')
    expect(wrapper.text()).toContain('uses its own currency settings')
    await wrapper.findAll('button').find(b => b.text() === 'Company default').trigger('click')
    await flushPromises()
    expect(save).toHaveBeenCalledWith(null)
  })

  it('cannot pick multiple currencies when none are set up', () => {
    const { wrapper } = mountBar({ company: { ...company(), others: [] } })
    expect(wrapper.find('option[value="multiple"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Add other currencies')
  })

  it('saves the full options for this campaign and shows the server reason on failure', async () => {
    const save = vi.fn().mockRejectedValue({ response: { data: { 'others.0.rate': ['Enter how much USD one AED buys (more than 0).'] } } })
    const { wrapper } = mountBar({ save })
    await wrapper.findAll('button').find(b => b.text() === 'More options').trigger('click')
    await wrapper.findAll('button').find(b => b.text() === 'Save for this campaign').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('Enter how much USD one AED buys')
    expect(wrapper.findAll('button').some(b => b.text() === 'Save for this campaign')).toBe(true)
  })

  it('is read-only without permission to change campaigns', () => {
    useAuthStore().user.permissions = { 'campaigns.campaigns.view': 'all' }
    const { wrapper } = mountBar()
    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('button').some(b => b.text() === 'More options')).toBe(false)
  })
})
