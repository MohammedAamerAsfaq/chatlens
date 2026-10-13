import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PropertyAttributeFields from '../components/PropertyAttributeFields.vue'

const definitions = [
  { code: 'ac_type', label: 'AC type', data_type: 'select', options: ['central', 'district_cooling'], is_active: true },
  {
    code: 'district_cooling_company', label: 'District cooling company', data_type: 'text',
    condition_field: 'ac_type', condition_value: 'district_cooling', is_active: true,
  },
  { code: 'facilities', label: 'Facilities', data_type: 'list', is_active: true },
]

const stubs = {
  UiFormField: { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
  UiInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  UiSelect: { props: ['modelValue'], template: '<select />' },
}

describe('Real Estate property attributes', () => {
  it('shows conditional schema fields only when their condition matches', async () => {
    const wrapper = mount(PropertyAttributeFields, {
      props: { definitions, modelValue: { ac_type: 'central' } },
      global: { stubs },
    })
    expect(wrapper.text()).not.toContain('District cooling company')
    await wrapper.setProps({ modelValue: { ac_type: 'district_cooling' } })
    expect(wrapper.text()).toContain('District cooling company')
  })

  it('normalizes comma-separated list input before emitting', async () => {
    const wrapper = mount(PropertyAttributeFields, {
      props: { definitions: [definitions[2]], modelValue: {} },
      global: { stubs },
    })
    await wrapper.find('input').setValue('Pool, Gym')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([{ facilities: ['Pool', 'Gym'] }])
  })
})
