export function emptyProperty() {
  return {
    reference_code: '', title: '', property_type: 'apartment', description: '', bedrooms: '', bathrooms: '',
    built_up_area: '', plot_area: '', area_unit: 'sqft', furnishing: 'unknown', completion_status: 'unknown',
    developer: '', project_name: '', completion_year: '', availability_status: 'draft',
    market_scope: 'local', inventory_source_type: 'own', is_tracked: false,
    ownership_eligibility: 'all', tenure_type: '', parent: null, attributes: {},
    address: emptyAddress(),
  }
}

export function emptyAddress() {
  return {
    country: '', state_region: '', city: '', community: '', project_building: '', street: '',
    unit_number: '', postal_code: '', latitude: '', longitude: '', normalized_location: '',
    country_master: null, administrative_area_master: null, city_master: null,
    locality_master: null, development_master: null,
  }
}

export function emptyListing() {
  return {
    property: '', listing_type: 'sale', asking_price: '', currency: 'AED', payment_frequency: 'not_applicable',
    deposit: '', commission: '', payment_terms: '', available_from: '', status: 'draft', is_verified: false,
  }
}

export function cleanPayload(values, numericFields = []) {
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [
    key,
    numericFields.includes(key) && value === '' ? null : value,
  ]))
}
