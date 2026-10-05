import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import InquiryCardBody from '../components/InquiryCardBody.vue'
import InquiryCardReview from '../components/InquiryCardReview.vue'
import InquiryProductsDialog from '../components/InquiryProductsDialog.vue'
import MatchFixDialog from '../components/MatchFixDialog.vue'

const teleportHost = document.createElement('div')
teleportHost.id = 'ui-teleport-host'
document.body.append(teleportHost)

const hint = {
  index: 0,
  name: 'Phone',
  product: { name: 'Phone', qty: 2 },
  icon: '✓',
  availabilityLabel: 'in stock',
  createLabel: 'Create',
}

describe('Trading workflow components', () => {
  it('emits inquiry body row and stock actions', async () => {
    const wrapper = mount(InquiryCardBody, { props: { inquiry: { summary: 'WTB phone' }, hints: [hint] } })
    await wrapper.find('.body-row').trigger('click')
    expect(wrapper.emitted('toggle-row')?.[0]).toEqual(['summary'])
    await wrapper.find('.actions .verify').trigger('click')
    expect(wrapper.emitted('verify')?.[0][0]).toMatchObject({ index: 0 })
  })

  it('emits review changes without owning inquiry state', async () => {
    const wrapper = mount(InquiryCardReview, { props: { rating: 5, incorrectOpen: true, incorrectReason: '' } })
    await wrapper.get('input').setValue('Wrong model')
    expect(wrapper.emitted('update:incorrectReason')?.at(-1)).toEqual(['Wrong model'])
    await wrapper.find('.rating button').trigger('click')
    expect(wrapper.emitted('rate')?.[0]).toEqual([1])
  })

  it('routes match search actions from the modal', async () => {
    const wrapper = mount(MatchFixDialog, { props: { target: { lines: [{ index: 0, name: 'Phone' }] }, activeLine: { index: 0, name: 'Phone' }, drag: { x: 0, y: 0 }, products: [] }, attachTo: document.body })
    const search = document.body.querySelector('.search-row input')
    search.value = 'iPhone'
    search.dispatchEvent(new Event('input'))
    expect(wrapper.emitted('update:query')?.at(-1)).toEqual(['iPhone'])
    wrapper.unmount()
  })

  it('emits product creation from inquiry product management', async () => {
    const line = { index: 0, canonical_name: 'Phone', valid: true }
    const wrapper = mount(InquiryProductsDialog, { props: { open: true, lines: [line] }, attachTo: document.body })
    const button = [...document.body.querySelectorAll('.actions button')].find(node => node.textContent.includes('Create Product'))
    button.click()
    expect(wrapper.emitted('create-product')?.[0][0]).toMatchObject({ index: 0 })
    wrapper.unmount()
  })
})
