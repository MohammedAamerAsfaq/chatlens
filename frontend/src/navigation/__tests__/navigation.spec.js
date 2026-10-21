import { describe, expect, it } from 'vitest'
import { industryHomePath, navigationItemVisible, primaryNavigation, settingsNavigation } from '../navigation'

const context = industry => ({ industry, canManageTenants: false, hasPermission: () => true })

describe('industry-aware navigation', () => {
  it('shows Real Estate inventory and hides Trading modules for a Real Estate company', () => {
    const visible = primaryNavigation.filter(item => navigationItemVisible(item, context('real_estate')))
    expect(visible.map(item => item.id)).toContain('real-estate')
    expect(visible.map(item => item.id)).not.toContain('trading')
    expect(visible.map(item => item.id)).not.toContain('campaigns')
  })

  it('preserves Trading navigation for Trading companies', () => {
    const visible = primaryNavigation.filter(item => navigationItemVisible(item, context('trading')))
    expect(visible.map(item => item.id)).toContain('trading')
    expect(visible.map(item => item.id)).not.toContain('real-estate')
  })

  it('hides Trading-only settings from Real Estate companies', () => {
    const visible = settingsNavigation.filter(item => navigationItemVisible(item, context('real_estate')))
    expect(visible.map(item => item.route)).not.toContain('v2-settings')
    expect(visible.map(item => item.route)).toContain('ai-instructions')
    expect(visible.map(item => item.route)).toContain('ai-providers')
    expect(visible.map(item => item.route)).toContain('real-estate-mock-data')
  })

  it('keeps AI Instructions in Trading settings', () => {
    const visible = settingsNavigation.filter(item => navigationItemVisible(item, context('trading')))
    expect(visible.map(item => item.route)).toContain('ai-instructions')
  })

  it('lands a switched Real Estate company on its opportunity board', () => {
    expect(industryHomePath('real_estate')).toBe('/real-estate')
    expect(industryHomePath('trading')).toBe('/')
  })
})

describe('company-admin-gated navigation', () => {
  const adminContext = isCompanyAdmin => ({ industry: 'trading', canManageTenants: false, isCompanyAdmin, hasPermission: () => true })

  it('hides API Consumer settings from non-admins', () => {
    const visible = settingsNavigation.filter(item => navigationItemVisible(item, adminContext(false)))
    expect(visible.map(item => item.route)).not.toContain('api-consumer-settings')
  })

  it('shows API Consumer settings to company admins, including control-account admins', () => {
    const visible = settingsNavigation.filter(item => navigationItemVisible(item, adminContext(true)))
    expect(visible.map(item => item.route)).toContain('api-consumer-settings')
  })
})
