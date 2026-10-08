import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UiDataTableInlineEditor from '../UiDataTableInlineEditor.vue'

const options = [
  { value: 1, label: 'First' },
  { value: 2, label: 'Second' },
]

describe('UiDataTableInlineEditor', () => {
  it('edits a single value in place', async () => {
    const wrapper = mount(UiDataTableInlineEditor, {
      props: { modelValue: 1, options },
    })

    await wrapper.get('.ui-inline-editor__value').trigger('click')
    await wrapper.get('select').setValue('2')

    expect(wrapper.emitted('save')?.[0]).toEqual([2])
  })

  it('saves multiple selected values together', async () => {
    const wrapper = mount(UiDataTableInlineEditor, {
      props: { modelValue: [1], options, multiple: true },
    })

    await wrapper.get('.ui-inline-editor__value').trigger('click')
    await wrapper.findAll('input')[1]!.setValue(true)
    await wrapper.findAll('.ui-inline-editor__actions button')[1]!.trigger('click')

    expect(wrapper.emitted('save')?.[0]).toEqual([[1, 2]])
  })
})
