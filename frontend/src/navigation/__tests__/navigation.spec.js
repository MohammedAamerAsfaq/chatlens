import { describe, expect, it } from 'vitest'
import { industryHomePath, logsNavigation, navigationItemVisible, primaryNavigation, settingsNavigation } from '../navigation'

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

describe('permission-gated navigation', () => {
  // Menus follow permissions, never role names.
  const grantedContext = granted => ({ industry: 'trading', canManageTenants: false, hasPermission: code => granted.includes(code) })
  const ALL_BUT = missing => ({ industry: 'trading', canManageTenants: false, hasPermission: code => code !== missing })

  it('shows API Consumer and AI Providers only with settings.company.manage', () => {
    const hidden = settingsNavigation.filter(item => navigationItemVisible(item, ALL_BUT('settings.company.manage')))
    const shown = settingsNavigation.filter(item => navigationItemVisible(item, grantedContext(['settings.company.manage'])))
    expect(hidden.map(item => item.route)).not.toContain('api-consumer-settings')
    expect(hidden.map(item => item.route)).not.toContain('ai-providers')
    expect(shown.map(item => item.route)).toContain('api-consumer-settings')
    expect(shown.map(item => item.route)).toContain('ai-providers')
  })

  it('shows AI Operations only with settings.company.manage', () => {
    expect(logsNavigation.filter(item => navigationItemVisible(item, ALL_BUT('settings.company.manage'))).map(item => item.route)).not.toContain('ai-operations')
    expect(logsNavigation.filter(item => navigationItemVisible(item, grantedContext(['settings.company.manage']))).map(item => item.route)).toContain('ai-operations')
  })

  it('shows Products, Non-Inventory and Price Updates only with trading.products.view', () => {
    const trading = primaryNavigation.find(item => item.id === 'trading')
    const without = trading.children.filter(item => navigationItemVisible(item, ALL_BUT('trading.products.view'))).map(item => item.route)
    const withIt = trading.children.filter(item => navigationItemVisible(item, grantedContext(['trading.products.view']))).map(item => item.route)
    for (const route of ['products', 'non-inventory-products', 'product-price-update']) {
      expect(without).not.toContain(route)
      expect(withIt).toContain(route)
    }
    expect(without).toContain('trading')
  })
})

describe('personal settings', () => {
  const memberContext = (granted) => ({
    industry: 'trading', canManageTenants: false,
    hasPermission: code => granted.includes(code),
  })

  it('shows Sessions and Inquiry Sharing without company settings access', async () => {
    const { visibleSettingsNavigation } = await import('../navigation')
    const visible = visibleSettingsNavigation(memberContext(['conversations.accounts.view', 'trading.board.view']))
    expect(visible.map(item => item.route)).toEqual(['sessions', 'inquiry-sharing'])
  })

  it('still needs each personal item own permission', async () => {
    const { visibleSettingsNavigation } = await import('../navigation')
    expect(visibleSettingsNavigation(memberContext(['conversations.accounts.view'])).map(item => item.route)).toEqual(['sessions'])
    expect(visibleSettingsNavigation(memberContext([]))).toEqual([])
  })

  it('shows company settings only with settings.company.view', async () => {
    const { visibleSettingsNavigation } = await import('../navigation')
    const visible = visibleSettingsNavigation(memberContext(['settings.company.view', 'conversations.accounts.view']))
    expect(visible.map(item => item.route)).toContain('storage')
  })
})
