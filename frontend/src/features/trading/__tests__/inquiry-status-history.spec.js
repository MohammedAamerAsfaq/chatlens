import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import InquiryCardHeader from '../components/InquiryCardHeader.vue'

const base = { id: 1, inquiry_type: 'buy', status: 'price_high', is_shared: false, shared_by: [], shared_handling: [] }
const change = (byOwner) => ({
  user_name: 'Boss', by_owner: byOwner, status_label: 'Price High', source: 'update', created_at: '2026-11-14T10:05:00Z',
})

describe('Inquiry status history on cards', () => {
  it('points out a status set by someone other than the account owner', async () => {
    const wrapper = mount(InquiryCardHeader, { props: { inquiry: { ...base, status_change: change(false) } } })
    expect(wrapper.find('.set-by').text()).toContain('Set by Boss · Price High')
    expect(wrapper.find('.history').exists()).toBe(false)
    await wrapper.find('.set-by').trigger('click')
    expect(wrapper.emitted('history')).toHaveLength(1)
  })

  it('offers the history quietly when the owner made the change', async () => {
    const wrapper = mount(InquiryCardHeader, { props: { inquiry: { ...base, status_change: change(true) } } })
    expect(wrapper.find('.set-by').exists()).toBe(false)
    await wrapper.find('.history').trigger('click')
    expect(wrapper.emitted('history')).toHaveLength(1)
  })

  it('shows nothing before any change is recorded', () => {
    const wrapper = mount(InquiryCardHeader, { props: { inquiry: { ...base, status_change: null } } })
    expect(wrapper.find('.set-by').exists()).toBe(false)
    expect(wrapper.find('.history').exists()).toBe(false)
  })
})
