import { describe, expect, it } from 'vitest'
import { DEFAULT_CURRENCY_SETTINGS, formatCampaignPrice, settingsFor, suggestSymbol } from '../currency'

const settings = (changes = {}) => ({
  ...DEFAULT_CURRENCY_SETTINGS,
  primary: { code: 'AED', symbol: 'د.إ' },
  others: [
    { code: 'USD', symbol: '$', rate: 0.2723, enabled: true },
    { code: 'SAR', symbol: 'SAR', rate: 1.02, enabled: true },
    { code: 'EUR', symbol: '€', rate: 0.25, enabled: false },
  ],
  ...changes,
})

describe('campaign price display', () => {
  it('shows a single currency by default', () => {
    expect(formatCampaignPrice('27.00', 'AED')).toBe('AED 27')
    expect(formatCampaignPrice(6580, 'AED')).toBe('AED 6,580')
    expect(formatCampaignPrice(null, 'AED')).toBe('-')
  })

  it('adds each enabled currency converted from the primary price', () => {
    expect(formatCampaignPrice(27, 'AED', settings())).toBe('AED 27 / USD 7.35 / SAR 27.54')
  })

  it('uses symbols, places the label after the amount and keeps fixed decimals', () => {
    expect(formatCampaignPrice(27, 'AED', settings({ label: 'symbol' }))).toBe('د.إ 27 / $ 7.35 / SAR 27.54')
    expect(formatCampaignPrice(27, 'AED', settings({ label_position: 'suffix', trim_zeros: false, separator: ' | ' })))
      .toBe('27.00 AED | 7.35 USD | 27.54 SAR')
    expect(formatCampaignPrice(27, 'AED', settings({ label: 'none', decimals: 0 }))).toBe('27 / 7 / 28')
  })

  it('converts a price held in another listed currency to the primary first', () => {
    expect(formatCampaignPrice(100, 'USD', settings({ others: [{ code: 'USD', symbol: '$', rate: 0.25, enabled: true }] })))
      .toBe('AED 400 / USD 100')
  })

  it('shows a price in an unlisted currency as is', () => {
    expect(formatCampaignPrice(50, 'GBP', settings())).toBe('GBP 50')
  })

  it("prefers the campaign's own settings over the company's", () => {
    const company = settings()
    expect(settingsFor({ currency_settings: null }, company)).toBe(company)
    const own = settings({ others: [] })
    expect(settingsFor({ currency_settings: own }, company)).toBe(own)
  })

  it('suggests a symbol from the currency code', () => {
    expect(suggestSymbol('usd')).toBe('$')
    expect(suggestSymbol('XYZ')).toBe('')
    expect(suggestSymbol('dollar')).toBe('')
  })
})
