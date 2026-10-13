import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import UiCheckboxGroup from '../UiCheckboxGroup.vue'
import UiRadioGroup from '../UiRadioGroup.vue'

const options = [
  { value: 'one', label: 'One' },
  { value: 'two', label: 'Two' },
]

describe('UI choice groups', () => {
  it('emits one selected radio value', async () => {
    const wrapper = mount(UiRadioGroup, { props: { modelValue: 'one', options } })
    await wrapper.findAll('input')[1].trigger('change')
    expect(wrapper.emitted('update:modelValue')).toEqual([['two']])
  })

  it('adds and removes checkbox values without losing other selections', async () => {
    const wrapper = mount(UiCheckboxGroup, { props: { modelValue: ['one'], options } })
    await wrapper.findAll('input')[1].setValue(true)
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['one', 'two']])
    await wrapper.setProps({ modelValue: ['one', 'two'] })
    await wrapper.findAll('input')[0].setValue(false)
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([['two']])
  })
})
