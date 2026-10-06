import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import UiCheckbox from '../UiCheckbox.vue'
import UiDatePicker from '../UiDatePicker.vue'
import UiInput from '../UiInput.vue'
import UiModal from '../UiModal.vue'
import UiSelect from '../UiSelect.vue'
import UiToggle from '../UiToggle.vue'

describe('shared UI controls', () => {
  it('renders text inputs with the reusable visible-control classes and attributes', () => {
    const wrapper = mount(UiInput, { props: { modelValue: '', placeholder: 'Client name' }, attrs: { required: true } })
    const input = wrapper.get('input')
    expect(input.classes()).toContain('ui-control')
    expect(input.classes()).toContain('ui-input')
    expect(input.attributes('required')).toBeDefined()
    expect(input.attributes('placeholder')).toBe('Client name')
  })

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

  it('maps a searchable select value back to its original value type', async () => {
    const wrapper = mount(UiSelect, {
      props: { modelValue: 1, searchable: true, options: [{ value: 1, label: 'One' }, { value: 2, label: 'Two' }] },
    })
    await wrapper.get('select').setValue('2')
    const changes = wrapper.emitted('update:modelValue') || []
    expect(changes[changes.length - 1]).toEqual([2])
    wrapper.unmount()
  })

  it('exposes searchable select terms for remote filtering', async () => {
    const wrapper = mount(UiSelect, {
      props: { searchable: true, options: [{ value: 1, label: 'One' }] },
    })
    await nextTick()
    await nextTick()
    wrapper.get('select').element.dispatchEvent(new CustomEvent('search', {
      detail: { value: 'aamer' },
    }))
    expect(wrapper.emitted('search')?.[0]).toEqual(['aamer'])
    wrapper.unmount()
  })

  it('renders a reusable date-time picker with a readable alternate input', () => {
    const host = document.createElement('div')
    host.id = 'ui-teleport-host'
    document.body.append(host)
    const wrapper = mount(UiDatePicker, { props: { modelValue: '2026-10-06T15:30', mode: 'datetime' } })
    expect(wrapper.find('.ui-date-picker__input').exists()).toBe(true)
    expect((wrapper.get('input[type="hidden"]').element as HTMLInputElement).value).toBe('2026-10-06T15:30')
    wrapper.unmount()
    host.remove()
  })
})
