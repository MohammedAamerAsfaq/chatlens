import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CustomizerChoiceGroup from '@/components/navigation/CustomizerChoiceGroup.vue'
import { DEFAULT_INSPINIA_CONFIG, inspiniaClasses, inspiniaClassNames, normalizeInspiniaConfig } from '../inspinia.js'

describe('Inspinia configuration', () => {
  it('fills missing settings with stable defaults', () => {
    expect(normalizeInspiniaConfig({ skin: 'modern' })).toEqual({
      ...DEFAULT_INSPINIA_CONFIG,
      skin: 'modern',
    })
  })

  it('maps persisted settings to shell classes', () => {
    const classes = inspiniaClasses({
      sidenav_size: 'on_hover',
      sidebar_user: false,
      direction: 'rtl',
    })
    expect(classes).toContain('sidenav-size-on-hover')
    expect(classes).toContainEqual({ 'sidebar-user-hidden': true })
    expect(inspiniaClassNames({ sidebar_user: false })).toContain('sidebar-user-hidden')
  })

  it('uses stable public URLs for customizer previews', () => {
    const wrapper = mount(CustomizerChoiceGroup, {
      props: { title: 'Select Skin', setting: 'skin', values: ['galaxy'], selected: 'galaxy' },
    })
    expect(wrapper.get('img').attributes('src')).toBe('/inspinia-previews/skin-galaxy.png')
  })

  it('uses the static preview base supplied by Django', () => {
    const meta = document.createElement('meta')
    meta.name = 'chatlens-inspinia-preview-base'
    meta.content = '/static/frontend/inspinia-previews/'
    document.head.append(meta)
    const wrapper = mount(CustomizerChoiceGroup, {
      props: { title: 'Color Scheme', setting: 'color_scheme', values: ['dark'], selected: 'dark' },
    })
    expect(wrapper.get('img').attributes('src')).toBe('/static/frontend/inspinia-previews/theme-dark.png')
    meta.remove()
  })
})
