import { realEstateApi } from '@/api'
import { cleanPayload } from './forms'

export async function persistProperty(values, record = null) {
  const { address, ...propertyValues } = values
  const numeric = ['bedrooms', 'bathrooms', 'built_up_area', 'plot_area', 'completion_year']
  const response = record
    ? await realEstateApi.updateProperty(record.id, cleanPayload(propertyValues, numeric))
    : await realEstateApi.createProperty(cleanPayload(propertyValues, numeric))
  const addressPayload = cleanPayload(address, ['latitude', 'longitude'])
  const hasAddress = Object.values(address).some(value => value !== '' && value != null)
  if (response.data.address?.id) {
    await realEstateApi.updateAddress(response.data.address.id, addressPayload)
  } else if (hasAddress) {
    await realEstateApi.createAddress({ ...addressPayload, property: response.data.id })
  }
  return response.data
}
