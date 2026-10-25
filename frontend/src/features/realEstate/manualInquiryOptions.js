import { opportunityLanes, opportunityStatuses } from './boardOptions'

export const activityOptions = opportunityLanes.map(lane => ({
  value: lane.key,
  label: lane.label,
}))

export const scopeOptions = [
  { value: 'local', label: 'Local' },
  { value: 'regional', label: 'Regional' },
  { value: 'international', label: 'International' },
]

export const statusOptions = opportunityStatuses

export function emptyInquiryItem() {
  return {
    title: '', property_type: '', locations: [], reference_code: '',
    bedrooms_min: '', bedrooms_max: '', bathrooms_min: '', bathrooms_max: '',
    area_min: '', area_max: '', area_unit: 'sqft', amount_min: '', amount_max: '',
    currency: 'AED', furnishing: 'unknown', ownership_eligibility: 'all',
    tenure_type: '', timeframe: '', required_amenities: [],
    preferred_amenities: [], free_form_constraints: '', description: '',
    available_from: '', attributes: {},
  }
}
