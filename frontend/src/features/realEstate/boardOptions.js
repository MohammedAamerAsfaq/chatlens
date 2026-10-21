import { title } from '@/features/realEstate/options'

export const opportunityLanes = [
  {
    key: 'buying',
    label: 'Buying',
    shortLabel: 'Buy',
    description: 'Buyer requirements for property acquisition.',
    side: 'demand',
    tone: 'buying',
  },
  {
    key: 'selling',
    label: 'Selling',
    shortLabel: 'Sell',
    description: 'Properties offered for sale by owners or agents.',
    side: 'supply',
    tone: 'selling',
  },
  {
    key: 'leasing_inquiry',
    label: 'Leasing Inquiries',
    shortLabel: 'Rent',
    description: 'Tenant requirements for rental properties.',
    side: 'demand',
    tone: 'lease-inquiry',
  },
  {
    key: 'leasing_offer',
    label: 'Leasing Offers',
    shortLabel: 'Let',
    description: 'Properties offered for lease by landlords or agents.',
    side: 'supply',
    tone: 'lease-offer',
  },
]

export const opportunityStatuses = [
  'new', 'qualified', 'matched', 'contacted', 'viewing',
  'negotiation', 'won', 'lost', 'irrelevant',
].map(value => ({ value, label: title(value) }))

export const statusFilters = [
  { value: '', label: 'All statuses' },
  ...opportunityStatuses,
]

export function statusTone(status) {
  if (status === 'won') return 'success'
  if (['lost', 'irrelevant'].includes(status)) return 'danger'
  if (['matched', 'viewing', 'negotiation'].includes(status)) return 'warning'
  return status === 'new' ? 'info' : 'neutral'
}

export function opportunityParty(item) {
  return item.contact_name || item.contact_phone || item.source_chat_name || 'Unknown party'
}

export function opportunityFacts(item) {
  return item.requirement ? requirementFacts(item.requirement) : candidateFacts(item.property_candidate)
}

function requirementFacts(record) {
  if (!record) return []
  return compact([
    listFact(record.acceptable_locations),
    listFact(record.acceptable_property_types),
    rangeFact('Beds', record.bedrooms_min, record.bedrooms_max),
    moneyRange(record.currency, record.budget_min, record.budget_max),
    record.timeframe,
  ])
}

function candidateFacts(record) {
  if (!record) return []
  return compact([
    record.property_type ? title(record.property_type) : '',
    record.location_raw,
    record.bedrooms != null ? `${cleanNumber(record.bedrooms)} beds` : '',
    money(record.currency, record.asking_price),
  ])
}

export function formatDate(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  }).format(new Date(value))
}

export function money(currency, value) {
  if (value == null || value === '') return ''
  return `${currency || 'AED'} ${Number(value).toLocaleString()}`
}

function moneyRange(currency, low, high) {
  if (low == null && high == null) return ''
  if (low != null && high != null) return `${money(currency, low)} - ${Number(high).toLocaleString()}`
  return low != null ? `From ${money(currency, low)}` : `Up to ${money(currency, high)}`
}

function rangeFact(label, low, high) {
  if (low == null && high == null) return ''
  if (low != null && high != null) return `${label} ${cleanNumber(low)}-${cleanNumber(high)}`
  return `${label} ${cleanNumber(low ?? high)}${low == null ? ' max' : '+'}`
}

function listFact(value) {
  return Array.isArray(value) ? value.filter(Boolean).slice(0, 2).join(', ') : ''
}

function cleanNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })
}

function compact(values) {
  return values.filter(value => value !== '' && value != null)
}
