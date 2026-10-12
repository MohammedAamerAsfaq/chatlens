export const propertyStatuses = options(['draft', 'available', 'reserved', 'sold', 'leased', 'inactive'])
export const furnishingOptions = options(['unknown', 'unfurnished', 'semi_furnished', 'furnished'])
export const completionOptions = options(['unknown', 'ready', 'off_plan', 'under_construction'])
export const areaUnits = [
  { value: 'sqft', label: 'Square feet' }, { value: 'sqm', label: 'Square metres' },
  { value: 'sqyd', label: 'Square yards' }, { value: 'acre', label: 'Acres' },
  { value: 'hectare', label: 'Hectares' },
]
export const listingTypes = [{ value: 'sale', label: 'Sale' }, { value: 'lease', label: 'Lease' }]
export const listingStatuses = options(['draft', 'active', 'paused', 'expired', 'closed'])
export const paymentFrequencies = options(['not_applicable', 'yearly', 'monthly', 'quarterly', 'weekly', 'daily'])
export const mediaTypes = options(['image', 'video', 'floor_plan', 'brochure', 'document'])

export function title(value) {
  return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

function options(values) {
  return values.map(value => ({ value, label: title(value) }))
}
