import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import InspiniaTopbarMenus from '../InspiniaTopbarMenus.vue'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

describe('InspiniaTopbarMenus', () => {
  it('keeps Apps open while navigating to the panel and closes on outside click', async () => {
    const wrapper = mount(InspiniaTopbarMenus, {
      attachTo: document.body,
      props: { apps: [{ route: 'settings', to: '/settings', label: 'Settings' }] },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.find('.apps-panel').exists()).toBe(true)

    await wrapper.find('.topbar-menus').trigger('mouseleave')
    expect(wrapper.find('.apps-panel').exists()).toBe(true)

    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    await nextTick()
    expect(wrapper.find('.apps-panel').exists()).toBe(false)
    wrapper.unmount()
  })
})
