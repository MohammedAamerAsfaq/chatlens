import { describe, expect, it } from 'vitest'
import { DEFAULT_INSPINIA_CONFIG, inspiniaClasses, normalizeInspiniaConfig } from '../inspinia.js'

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
  })
})
