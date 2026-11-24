// Location of an inquiry's properties, from the Real Estate Location step or set by hand
// (apps/real_estate/services/location_service.py).

export function locatedItems(opportunity) {
  return (opportunity?.items || []).filter(item => item.geo_status === 'located' && item.geo_area)
}

export function itemPlace(item) {
  const parts = [item.geo_sub_area, item.geo_area, item.geo_city].filter(Boolean)
  return [...new Set(parts)].join(', ')
}

// "DAMAC Hills 2, Dubai" for one property; several properties are joined with " / ".
export function opportunityPlace(opportunity) {
  return [...new Set(locatedItems(opportunity).map(itemPlace))].join(' / ')
}

// Google Maps link: the area's map position when it has one, otherwise a search for its name.
export function googleMapsUrl(item) {
  const position = item.geo_position
  const query = position?.status === 'placed' && position.latitude != null
    ? `${position.latitude},${position.longitude}`
    : itemPlace(item)
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}
