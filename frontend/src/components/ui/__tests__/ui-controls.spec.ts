import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UiCheckbox from '../UiCheckbox.vue'
import UiModal from '../UiModal.vue'
import UiToggle from '../UiToggle.vue'

describe('shared UI controls', () => {
  it('emits checkbox and toggle state changes', async () => {
    const checkbox = mount(UiCheckbox, { props: { modelValue: false, label: 'Enabled' } })
    await checkbox.get('input').setValue(true)
    expect(checkbox.emitted('update:modelValue')?.[0]).toEqual([true])

    const toggle = mount(UiToggle, { props: { modelValue: false, label: 'Enabled' } })
    await toggle.get('button').trigger('click')
    expect(toggle.emitted('update:modelValue')?.[0]).toEqual([true])
  })

  it('closes an open modal with Escape', async () => {
    const wrapper = mount(UiModal, { props: { open: true, title: 'Review' }, attachTo: document.body })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })
})
