import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ areaMap: vi.fn(), placeAreas: vi.fn() }))
const maps = vi.hoisted(() => ({ markers: [], fitBounds: vi.fn() }))
vi.mock('@/api', () => ({ realEstateApi: api }))
vi.mock('@/components/ui/UiDatePicker.vue', () => ({ default: { props: ['modelValue'], template: '<input />' } }))
vi.mock('@/features/realEstate/googleMapsLoader', () => ({
  loadGoogleMaps: () => Promise.resolve({
    Map: function Map() { return { fitBounds: maps.fitBounds, setCenter: vi.fn(), setZoom: vi.fn(), panTo: vi.fn(), getZoom: () => 9 } },
    InfoWindow: function InfoWindow() { return { setContent: vi.fn(), open: vi.fn() } },
    LatLngBounds: function LatLngBounds() { return { extend: vi.fn(), getCenter: vi.fn() } },
    Marker: function Marker(options) { const marker = { options, setMap: vi.fn(), addListener: vi.fn(), getPosition: () => options.position }; maps.markers.push(marker); return marker },
    SymbolPath: { CIRCLE: 0 },
  }),
}))

const report = (overrides = {}) => ({
  country: { name: 'United Arab Emirates', iso2: 'AE', latitude: 24, longitude: 54 },
  browser_api_key: 'browser-key', map_error: '',
  total_opportunities: 6, without_location: 1,
  areas: [
    { key: 'dubai marina', name: 'Dubai Marina', count: 4, by_activity: { buying: 3, selling: 1 }, status: 'placed', source: 'directory', latitude: 25.08, longitude: 55.14, matched_label: 'Dubai Marina, AE', error: '' },
    { key: 'jvc', name: 'JVC', count: 1, by_activity: { leasing_inquiry: 1 }, status: 'pending', source: '', latitude: null, longitude: null, matched_label: '', error: '' },
  ],
  google: { available: true, waiting: 1, batch: 20, usage: { remaining: 99, monthly_request_limit: 100 } },
  ...overrides,
})

async function mountView() {
  const { default: View } = await import('@/views/RealEstateAreaMapView.vue')
  const wrapper = mount(View)
  await flushPromises()
  return wrapper
}

describe('Area Map', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    maps.markers = []
    api.areaMap.mockResolvedValue({ data: report() })
  })

  it('ranks areas and draws a circle for each placed area, the busiest the biggest', async () => {
    const wrapper = await mountView()
    expect(api.areaMap).toHaveBeenCalledWith({ activity_type: 'all' })
    const ranking = wrapper.findAll('.area-map__ranking li')
    expect(ranking[0].text()).toContain('Dubai Marina')
    expect(ranking[0].text()).toContain('Buying: 3 · Selling: 1')
    expect(ranking[0].text()).toContain('80%')
    expect(ranking[1].text()).toContain('Not on the map: Not looked up on Google yet')
    expect(maps.markers).toHaveLength(1)
    expect(maps.markers[0].options.label.text).toBe('4')
    expect(maps.markers[0].options.icon.fillColor).toBe('#238b75')
    expect(wrapper.text()).toContain('1 without any location')
  })

  it('looks up the remaining areas on Google only when asked', async () => {
    api.placeAreas.mockResolvedValue({ data: { ...report({ google: { available: true, waiting: 0, batch: 20, usage: null } }), notice: '' } })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('99 of 100 left this month')
    await wrapper.findAll('button').find(b => b.text() === 'Find on Google Maps').trigger('click')
    await flushPromises()
    expect(api.placeAreas).toHaveBeenCalledWith({ activity_type: 'all' })
    expect(wrapper.text()).not.toContain('Find on Google Maps')
  })

  it('reloads for another inquiry type', async () => {
    const wrapper = await mountView()
    await wrapper.findAll('[role="tab"]').find(b => b.text() === 'Selling').trigger('click')
    await flushPromises()
    expect(api.areaMap).toHaveBeenLastCalledWith({ activity_type: 'selling' })
  })

  it('says why the map is missing instead of showing a blank box', async () => {
    api.areaMap.mockResolvedValue({ data: report({ browser_api_key: '', map_error: 'Configure and enable Google Maps with a browser API key in Integrations to show the map.' }) })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Configure and enable Google Maps')
    expect(wrapper.findAll('.area-map__ranking li')).toHaveLength(2)
  })
})
