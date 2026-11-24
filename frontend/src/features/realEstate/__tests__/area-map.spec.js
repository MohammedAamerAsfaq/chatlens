import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  areaMap: vi.fn(), placeAreas: vi.fn(), locateAreas: vi.fn(), mergeAreas: vi.fn(), getLocationSearch: vi.fn(), setLocationSearch: vi.fn(),
}))
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
  totals: { opportunities: 10, no_properties: 1, located: 5, unknown: 1, pending: 2, error: 1 },
  locating: 0,
  location_search_mode: 'model_knowledge',
  areas: [
    { id: 1, name: 'DAMAC Hills 2', city: 'Dubai', count: 4, by_activity: { buying: 3, selling: 1 }, sub_areas: [{ name: 'Verona', count: 3 }, { name: 'Camelia', count: 1 }], status: 'placed', source: 'google', latitude: 24.98, longitude: 55.39, matched_label: 'DAMAC Hills 2, Dubai', error: '' },
    { id: 2, name: 'Al Reem Island', city: 'Abu Dhabi', count: 1, by_activity: { leasing_inquiry: 1 }, sub_areas: [], status: 'pending', source: '', latitude: null, longitude: null, matched_label: '', error: '' },
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

const button = (wrapper, text) => wrapper.findAll('button').find(b => b.text().includes(text))

describe('Area Map', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    maps.markers = []
    api.areaMap.mockResolvedValue({ data: report() })
  })

  it('ranks areas with their buildings and draws a circle per placed area', async () => {
    const wrapper = await mountView()
    expect(api.areaMap).toHaveBeenCalledWith({ activity_type: 'all' })
    const ranking = wrapper.findAll('.area-map__ranking li')
    expect(ranking[0].text()).toContain('DAMAC Hills 2, Dubai')
    expect(ranking[0].text()).toContain('Verona 3 · Camelia 1')
    expect(ranking[0].text()).toContain('80%')
    expect(ranking[1].text()).toContain('Not on the map: Waiting for a Google Maps lookup')
    expect(maps.markers).toHaveLength(1)
    expect(maps.markers[0].options.label.text).toBe('4')
    expect(maps.markers[0].options.icon.fillColor).toBe('#238b75')
    expect(wrapper.text()).toContain('5 located in 2 areas')
    expect(wrapper.text()).toContain('2 not located yet')
  })

  it('queues the location AI for inquiries without an area', async () => {
    api.locateAreas.mockResolvedValue({ data: { ...report({ locating: 3, totals: { opportunities: 10, no_properties: 1, located: 5, unknown: 1, pending: 2, error: 1 } }), queued: 3 } })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('3 inquiries have no area yet')
    await button(wrapper, 'Find locations for 3').trigger('click')
    await flushPromises()
    expect(api.locateAreas).toHaveBeenCalledWith('unlocated', { activity_type: 'all' })
    expect(wrapper.text()).toContain('3 inquiries queued')
    expect(wrapper.text()).toContain('Locating 3 inquiries...')
  })

  it('asks before re-checking every inquiry', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await mountView()
    await button(wrapper, 'Re-check all').trigger('click')
    expect(confirm.mock.calls[0][0]).toContain('all 10 inquiries')
    expect(api.locateAreas).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('looks up waiting areas on Google only when asked', async () => {
    api.placeAreas.mockResolvedValue({ data: { ...report({ google: { available: true, waiting: 0, batch: 20, usage: null } }), notice: '' } })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('99 of 100 left this month')
    await button(wrapper, 'Find on Google Maps').trigger('click')
    await flushPromises()
    expect(api.placeAreas).toHaveBeenCalledWith({ activity_type: 'all' })
    expect(button(wrapper, 'Find on Google Maps')).toBeUndefined()
  })

  it('reloads for another inquiry type', async () => {
    const wrapper = await mountView()
    await wrapper.findAll('[role="tab"]').find(b => b.text() === 'Selling').trigger('click')
    await flushPromises()
    expect(api.areaMap).toHaveBeenLastCalledWith({ activity_type: 'selling' })
  })

  it('shows why the location step failed', async () => {
    api.areaMap.mockResolvedValue({ data: report({ error_reasons: [{ error: 'No active agent provider configured.', count: 508 }] }) })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Why the location step failed')
    expect(wrapper.text()).toContain('508 × No active agent provider configured.')
  })

  it('merges an area written another way into the right one', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.mergeAreas.mockResolvedValue({ data: { ...report(), merged: 1 } })
    const wrapper = await mountView()
    const second = wrapper.findAll('.area-map__ranking li')[1]
    await second.find('.area-map__merge-start').trigger('click')
    await second.find('select').setValue(1)
    await second.findAll('button').find(b => b.text() === 'Merge').trigger('click')
    await flushPromises()
    expect(confirm.mock.calls[0][0]).toContain('Merge "Al Reem Island, Abu Dhabi" into "DAMAC Hills 2, Dubai"')
    expect(api.mergeAreas).toHaveBeenCalledWith(2, 1, { activity_type: 'all' })
    expect(wrapper.text()).toContain('Merged "Al Reem Island" into "DAMAC Hills 2".')
    confirm.mockRestore()
  })

  it('says why the map is missing instead of showing a blank box', async () => {
    api.areaMap.mockResolvedValue({ data: report({ browser_api_key: '', map_error: 'Configure and enable Google Maps with a browser API key in Integrations to show the map.' }) })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Configure and enable Google Maps')
    expect(wrapper.findAll('.area-map__ranking li')).toHaveLength(2)
  })
})

describe('Location finding settings', () => {
  it('saves the chosen mode and shows why web search is not available', async () => {
    const choices = [{ value: 'model_knowledge', label: "AI's own market knowledge" }, { value: 'web_search', label: 'AI with live web search (OpenRouter)' }]
    api.getLocationSearch.mockResolvedValue({ data: { mode: 'model_knowledge', choices, web_search_blockers: ['DeepSeek (deepseek)'] } })
    api.setLocationSearch.mockRejectedValue({ response: { status: 400, data: { mode: ['Web search needs OpenRouter models'] } } })
    const { default: Settings } = await import('../components/LocationSearchSettings.vue')
    const wrapper = mount(Settings)
    await flushPromises()
    expect(wrapper.text()).toContain('Not available yet: the location AI uses DeepSeek (deepseek).')
    await wrapper.find('input[value="web_search"]').setValue(true)
    await button(wrapper, 'Save location finding').trigger('click')
    await flushPromises()
    expect(api.setLocationSearch).toHaveBeenCalledWith('web_search')
    expect(wrapper.find('[role="alert"]').text()).toContain('Web search needs OpenRouter models')
  })
})
