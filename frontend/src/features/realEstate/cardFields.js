// Registry of attributes an admin can choose to show on Opportunity Board cards
// (apps/real_estate/views_prompts.py card-field-config stores an ordered list of these
// ids). This file is the single source of truth for what each id means and how to pull
// its value off an opportunity row — the backend only ever stores/returns opaque ids.
import { formatDate, moneyRange, opportunityParty } from '@/features/realEstate/boardOptions'
import { title } from '@/features/realEstate/options'

function firstItem(opportunity) {
  return opportunity.items?.[0] || null
}

export const cardFields = [
  {
    id: 'party_name', label: 'Party Name', section: 'header',
    getValue: opportunity => opportunityParty(opportunity),
  },
  {
    id: 'sender', label: 'Sender', section: 'header',
    getValue: opportunity => opportunity.contact_phone || opportunity.source_chat_name || '',
  },
  {
    id: 'inquiry_type', label: 'Inquiry Type', section: 'body',
    getValue: opportunity => title(opportunity.activity_type || ''),
  },
  {
    id: 'property_type', label: 'Property Type', section: 'body',
    getValue: opportunity => {
      const item = firstItem(opportunity)
      return item ? (item.property_type_name || title(item.property_type_label || '')) : ''
    },
  },
  {
    id: 'location', label: 'Location', section: 'body',
    getValue: opportunity => firstItem(opportunity)?.location_raw || '',
  },
  {
    id: 'address_details', label: 'Address Details', section: 'body',
    // Only populated once this item is matched/linked to an inventory Property —
    // there's no separate address extracted from the inbound message itself.
    getValue: opportunity => firstItem(opportunity)?.property_title || '',
  },
  {
    id: 'property_value', label: 'Property Value', section: 'body',
    getValue: opportunity => {
      const item = firstItem(opportunity)
      return item ? moneyRange(item.currency, item.amount_min, item.amount_max) : ''
    },
  },
  {
    id: 'property_name', label: 'Property Name', section: 'body',
    getValue: opportunity => firstItem(opportunity)?.title || '',
  },
  {
    id: 'date_time', label: 'Date & Time', section: 'header',
    getValue: opportunity => opportunity.first_seen_at ? formatDate(opportunity.first_seen_at) : '',
  },
]

export const cardFieldsById = Object.fromEntries(cardFields.map(field => [field.id, field]))

// Today's hard-coded layout, used whenever a company has no card_field_config saved yet.
export const defaultCardFieldIds = [
  'party_name', 'date_time', 'property_type', 'location', 'property_value', 'sender',
]
