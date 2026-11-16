import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PasswordField from '../PasswordField.vue'

function field(modelValue, props = {}) {
  return mount(PasswordField, { props: { modelValue, username: 'shoeb', email: 'shoeb@x.test', ...props } })
}

describe('PasswordField', () => {
  it('rates a short or name-based password weak and a long mixed one strong', () => {
    expect(field('shoeb123').find('.strength').classes()).toContain('weak')
    expect(field('Harbor-Violet-58').find('.strength').classes()).toContain('strong')
    const checks = field('Harbor-Shoeb-58').findAll('.checks li')
    expect(checks.at(4).classes()).not.toContain('ok')
  })

  it('generates a strong 16-character password and shows it', async () => {
    const wrapper = field('')
    await wrapper.findAll('button').at(1).trigger('click')
    const generated = wrapper.emitted('update:modelValue')[0][0]
    expect(generated).toHaveLength(16)
    await wrapper.setProps({ modelValue: generated })
    expect(wrapper.find('.strength').classes()).toContain('strong')
    expect(wrapper.find('input').attributes('type')).toBe('text')
  })

  it('lists the server rules when given', () => {
    const wrapper = field('', { rules: ['Your password must contain at least 8 characters.'] })
    expect(wrapper.find('.rules').text()).toContain('at least 8 characters')
  })
})
