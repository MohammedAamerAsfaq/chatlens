import { describe, expect, it } from 'vitest'
import { industryHomePath, navigationItemVisible, primaryNavigation, settingsNavigation } from '../navigation'

const context = industry => ({ industry, canManageTenants: false, hasPermission: () => true })

describe('industry-aware navigation', () => {
  it('shows Real Estate inventory and hides Trading modules for a Real Estate company', () => {
    const visible = primaryNavigation.filter(item => navigationItemVisible(item, context('real_estate')))
    expect(visible.map(item => item.id)).toContain('real-estate')
    expect(visible.map(item => item.id)).not.toContain('trading')
    expect(visible.map(item => item.id)).not.toContain('campaigns')

    const realEstate = visible.find(item => item.id === 'real-estate')
    expect(realEstate.routes).toContain('ai-instructions')
    expect(realEstate.children.map(item => item.route)).toContain('ai-instructions')
  })

  it('preserves Trading navigation for Trading companies', () => {
    const visible = primaryNavigation.filter(item => navigationItemVisible(item, context('trading')))
    expect(visible.map(item => item.id)).toContain('trading')
    expect(visible.map(item => item.id)).not.toContain('real-estate')
  })

  it('hides Trading-only settings from Real Estate companies', () => {
    const visible = settingsNavigation.filter(item => navigationItemVisible(item, context('real_estate')))
    expect(visible.map(item => item.route)).not.toContain('v2-settings')
    expect(visible.map(item => item.route)).not.toContain('ai-instructions')
    expect(visible.map(item => item.route)).toContain('ai-providers')
    expect(visible.map(item => item.route)).toContain('real-estate-mock-data')
  })

  it('keeps AI Instructions in Trading settings', () => {
    const visible = settingsNavigation.filter(item => navigationItemVisible(item, context('trading')))
    expect(visible.map(item => item.route)).toContain('ai-instructions')
  })

  it('lands a switched Real Estate company on its inventory', () => {
    expect(industryHomePath('real_estate')).toBe('/real-estate/properties')
    expect(industryHomePath('trading')).toBe('/')
  })
})
