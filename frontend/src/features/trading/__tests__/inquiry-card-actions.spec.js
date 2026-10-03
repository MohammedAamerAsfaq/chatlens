import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import InquiryCardActions from '../components/InquiryCardActions.vue'

const inquiry = {
  id: 42,
  inquiry_type: 'buy',
  contact: 7,
  source_chat_id: 9,
  products: [{ id: 1 }],
}

describe('InquiryCardActions', () => {
  it('emits product and direct-chat actions', async () => {
    const wrapper = mount(InquiryCardActions, {
      props: { inquiry, manualMatchAvailable: true, waLink: 'https://wa.me/971500000000' },
    })
    await wrapper.find('.products-menu summary').trigger('click')
    await wrapper.find('.products-menu button').trigger('click')
    expect(wrapper.emitted('inquiry-products')).toHaveLength(1)

    await wrapper.find('.wa-menu summary').trigger('click')
    const directButton = wrapper.findAll('.wa-menu button').find(button => button.text().startsWith('ChatLens'))
    await directButton.trigger('click')
    expect(wrapper.emitted('wa-direct-chatlens')).toHaveLength(1)
  })

  it('only exposes price-list actions when enabled', () => {
    const disabled = mount(InquiryCardActions, { props: { inquiry, askPriceLink: 'https://wa.me/example' } })
    expect(disabled.text()).not.toContain('Price List')

    const enabled = mount(InquiryCardActions, {
      props: { inquiry, priceListEnabled: true, priceListLink: 'https://wa.me/list', formattedPriceListAvailable: true },
    })
    expect(enabled.text()).toContain('Price List - WA Client')
  })
})
