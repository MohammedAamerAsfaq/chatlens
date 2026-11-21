// How a campaign message shows a price: the primary currency, then each enabled other
// currency converted with its hand-entered rate (1 primary = rate x other). Settings come
// from the campaign's own currency_settings, else the company's (trading-settings/
// campaign-currency); see apps/trading/services/campaign_currency.py. The same settings say
// whether product lines show the brand in front of the product name (show_brand).

export const DEFAULT_CURRENCY_SETTINGS = Object.freeze({
  primary: { code: 'AED', symbol: 'AED' },
  label: 'code',
  label_position: 'prefix',
  decimals: 2,
  trim_zeros: true,
  separator: ' / ',
  others: [],
  show_brand: true,
})

// An editable copy; settings saved before a key existed take that key's default.
export function blankCurrencySettings(source = DEFAULT_CURRENCY_SETTINGS) {
  return JSON.parse(JSON.stringify({ ...DEFAULT_CURRENCY_SETTINGS, ...source }))
}

export const brandShown = settings => settings?.show_brand !== false

// {product_name} in a product line. row.product_name is the product as campaigns show it
// (brand in front, see serializers.product_display_name); hiding the brand drops that prefix.
export function campaignProductName(row, settings = DEFAULT_CURRENCY_SETTINGS) {
  const name = String(row?.product_name || '')
  const brand = String(row?.brand || '').trim()
  if (brandShown(settings) || !brand || !name.toLowerCase().startsWith(`${brand.toLowerCase()} `)) return name
  return name.slice(brand.length + 1).trim()
}

export function settingsFor(campaign, companySettings) {
  return campaign?.currency_settings || companySettings || DEFAULT_CURRENCY_SETTINGS
}

// The browser's own currency data suggests a symbol for a code (USD -> $); empty if unknown.
export function suggestSymbol(code) {
  const upper = String(code || '').trim().toUpperCase()
  if (!/^[A-Z]{3}$/.test(upper)) return ''
  try {
    const part = new Intl.NumberFormat('en', { style: 'currency', currency: upper, currencyDisplay: 'narrowSymbol' })
      .formatToParts(0).find(item => item.type === 'currency')
    return part && part.value !== upper ? part.value : ''
  } catch {
    return ''
  }
}

function amountText(value, settings) {
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: settings.trim_zeros ? 0 : settings.decimals,
    maximumFractionDigits: settings.decimals,
  })
}

function labelled(value, currency, settings) {
  const amount = amountText(value, settings)
  if (settings.label === 'none') return amount
  const label = settings.label === 'symbol' ? (currency.symbol || currency.code) : currency.code
  return settings.label_position === 'suffix' ? `${amount} ${label}` : `${label} ${amount}`
}

// amount is in rowCurrency (the product's currency; blank means the primary currency).
export function formatCampaignPrice(amount, rowCurrency, settings = DEFAULT_CURRENCY_SETTINGS) {
  if (amount === null || amount === undefined || amount === '' || Number.isNaN(Number(amount))) return '-'
  const primary = settings.primary
  const code = String(rowCurrency || primary.code).toUpperCase()
  let base = Number(amount)
  if (code !== primary.code) {
    const other = settings.others.find(row => row.code === code)
    // A price in a currency these settings can't convert is shown as is, in its own currency.
    if (!other) return labelled(base, { code, symbol: code }, settings)
    base /= other.rate
  }
  const parts = [labelled(base, primary, settings)]
  for (const other of settings.others) {
    if (other.enabled) parts.push(labelled(base * other.rate, other, settings))
  }
  return parts.join(settings.separator)
}
