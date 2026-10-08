import { describe, expect, it } from 'vitest'
import { primaryNavigation } from '../navigation'
import { pageDescription } from '../pageDescriptions'

describe('automation navigation', () => {
  it('keeps price automation in its own primary module', () => {
    const automation = primaryNavigation.find(item => item.id === 'automation')
    const trading = primaryNavigation.find(item => item.id === 'trading')

    expect(automation).toMatchObject({
      label: 'Automation',
      to: '/automation',
      routes: ['price-automation'],
    })
    expect(automation.children).toContainEqual({
      label: 'Price Automation',
      to: '/automation',
      route: 'price-automation',
    })
    expect(trading.routes).not.toContain('price-automation')
    expect(pageDescription('price-automation')).toContain('sale price automation')
  })
})
