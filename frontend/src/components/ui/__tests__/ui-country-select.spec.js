import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import UiCountrySelect from '../UiCountrySelect.vue'

const api = vi.hoisted(() => ({ countries: vi.fn() }))
vi.mock('@/api', () => ({ integrationsApi: api }))

const tenCountries = Array.from({ length: 10 }, (_, index) => ({ id: index + 1, iso2: `C${index}`, name: `Country ${index}` }))
const optionLabels = wrapper => [...new Set(wrapper.findAll('select option').map(option => option.text()))]

describe('UiCountrySelect', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    api.countries.mockReset()
    api.countries.mockResolvedValue({ data: tenCountries })
  })
  afterEach(() => vi.useRealTimers())

  it('shows the first 10 countries, then fetches matches as the user types', async () => {
    const wrapper = mount(UiCountrySelect, { props: { modelValue: null } })
    await flushPromises()
    expect(api.countries).toHaveBeenCalledWith('')
    expect(optionLabels(wrapper).filter(label => label.startsWith('Country'))).toHaveLength(10)

    api.countries.mockResolvedValue({ data: [{ id: 50, iso2: 'SD', name: 'Sudan' }, { id: 51, iso2: 'SS', name: 'South Sudan' }] })
    await nextTick(); await nextTick()
    wrapper.get('select').element.dispatchEvent(new CustomEvent('search', { detail: { value: 'su' } }))
    wrapper.get('select').element.dispatchEvent(new CustomEvent('search', { detail: { value: 'sud' } }))
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(api.countries).toHaveBeenCalledTimes(2)
    expect(api.countries).toHaveBeenLastCalledWith('sud')
    expect(optionLabels(wrapper)).toEqual(expect.arrayContaining(['Sudan', 'South Sudan']))

    await wrapper.get('select').setValue('50')
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([{ id: 50, iso2: 'SD', name: 'Sudan' }])
    wrapper.unmount()
  })

  it('keeps the saved country selectable and can clear it', async () => {
    const wrapper = mount(UiCountrySelect, { props: { modelValue: { id: 99, iso2: 'OM', name: 'Oman' } } })
    await flushPromises()
    expect(optionLabels(wrapper)).toEqual(expect.arrayContaining(['No country', 'Oman']))
    await wrapper.get('select').setValue('')
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([null])
    wrapper.unmount()
  })
})
