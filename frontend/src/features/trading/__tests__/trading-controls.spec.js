import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TradingFeedControls from '../components/TradingFeedControls.vue'
import TradingOverview from '../components/TradingOverview.vue'
import TradingToolbarSettings from '../components/TradingToolbarSettings.vue'
import InquiryCardHeader from '../components/InquiryCardHeader.vue'

const controlProps = {
  contactSearch: '',
  dateRange: 'today',
  dateOptions: [{ value: 'today', label: 'Today' }, { value: 'week', label: 'Week' }],
  sort: 'latest',
  pageSize: 25,
  pageSizeOptions: [25, 50],
}

describe('Trading feature controls', () => {
  it('emits query changes from feed controls', async () => {
    const wrapper = mount(TradingFeedControls, { props: controlProps })
    await wrapper.get('input').setValue('Aamer')
    expect(wrapper.emitted('update:contactSearch')?.at(-1)).toEqual(['Aamer'])
    expect(wrapper.emitted('search-contact')).toHaveLength(1)

    await wrapper.get('.sort-button').trigger('click')
    expect(wrapper.emitted('update:sort')?.at(-1)).toEqual(['oldest'])
    expect(wrapper.emitted('change-sort')).toHaveLength(1)

    await wrapper.get('.feed-select.compact').setValue('50')
    expect(wrapper.emitted('update:pageSize')?.at(-1)).toEqual([50])
    expect(wrapper.emitted('change-page-size')).toHaveLength(1)
  })

  it('renders compact activity metrics', () => {
    const wrapper = mount(TradingOverview, {
      props: {
        stats: { today: { wtb_total: 3, wts_total: 4 } },
      },
    })
    expect(wrapper.text()).toContain('WTB Today')
    expect(wrapper.findAll('.metric')).toHaveLength(5)
  })

  it('emits dashboard settings changes', async () => {
    const wrapper = mount(TradingToolbarSettings, {
      props: {
        accounts: [{ id: 7, display_name: 'Control Account' }],
        selectedAccount: '',
        closeStaleHours: 1,
      },
    })
    await wrapper.get('.icon-button').trigger('click')
    await wrapper.findAll('select')[0].setValue('7')
    expect(wrapper.emitted('update:selectedAccount')?.at(-1)).toEqual(['7'])
    expect(wrapper.emitted('change-account')).toHaveLength(1)

    await wrapper.get('input').setValue('2')
    expect(wrapper.emitted('update:closeStaleHours')?.at(-1)).toEqual([2])
    await wrapper.get('.stale-controls button').trigger('click')
    expect(wrapper.emitted('close-stale')).toHaveLength(1)
  })

  it('normalizes inquiry header status actions', async () => {
    const wrapper = mount(InquiryCardHeader, {
      props: {
        inquiry: { contact: 1, contact_name: 'Supplier', source_type: 'group', age_seconds: 75 },
        categoryValue: 'supplier',
        suggestionAvailable: true,
      },
    })
    await wrapper.find('.status-select').setValue('tracking')
    expect(wrapper.emitted('set-status')?.[0]).toEqual(['tracking'])
    expect(wrapper.find('.status-select').element.value).toBe('')
  })
})
