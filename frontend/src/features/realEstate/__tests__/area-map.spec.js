import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  areaMap: vi.fn(), areaMapInquiries: vi.fn(), locationStatus: vi.fn(), placeAreas: vi.fn(), locateAreas: vi.fn(), mergeAreas: vi.fn(), getLocationSearch: vi.fn(), setLocationSearch: vi.fn(),
}))
const maps = vi.hoisted(() => ({ markers: [], fitBounds: vi.fn() }))
vi.mock('@/api', () => ({ realEstateApi: api }))
vi.mock('@/components/ui/UiDatePicker.vue', () => ({ default: { props: ['modelValue'], template: '<input />' } }))
const whatsapp = vi.hoisted(() => ({ viewSource: vi.fn(), openInInbox: vi.fn() }))
vi.mock('@/features/realEstate/composables/useOpportunityWhatsApp', async () => {
  const { ref } = await import('vue')
  return {
    useOpportunityWhatsApp: () => ({
      dialog: { open: ref(false), loading: ref(false), error: ref(''), draft: ref(''), inquiry: ref(null), title: ref(''), close: vi.fn() },
      viewSource: whatsapp.viewSource, openInInbox: whatsapp.openInInbox,
    }),
  }
})
vi.mock('@/features/trading/components/TradingConversationDialog.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/features/realEstate/googleMapsLoader', () => ({
  loadGoogleMaps: () => Promise.resolve({
    Map: function Map() { return { fitBounds: maps.fitBounds, setCenter: vi.fn(), setZoom: vi.fn(), panTo: vi.fn(), getZoom: () => 9 } },
    InfoWindow: function InfoWindow() { return { setContent: vi.fn(), open: vi.fn(), close: vi.fn() } },
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

const inquiryRow = {
  id: 7, first_seen_at: '2026-11-20T10:00:00Z', activity_type: 'buying', status: 'new',
  summary: 'Wants a villa in Verona', original_message: 'Need villa Verona', contact_name: 'Abdul', contact_phone: '+971500000000',
  account: 3, source_chat: 11, source_chat_name: 'Dubai Brokers', source_message: 99, source_message_time: '2026-11-20T10:00:00Z',
  source_party_name: '', inquiry_medium_name: '',
  locations: [{ sequence: 1, status: 'located', area_id: 1, area: 'DAMAC Hills 2', sub_area: 'Verona', city: 'Dubai', location_raw: 'Verona', error: '' }],
}

async function mountView() {
  const { default: View } = await import('@/views/RealEstateAreaMapView.vue')
  const wrapper = mount(View, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  return wrapper
}

const button = (wrapper, text) => wrapper.findAll('button').find(b => b.text().includes(text))

describe('Area Map', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    maps.markers = []
    api.areaMap.mockResolvedValue({ data: report() })
    api.areaMapInquiries.mockResolvedValue({ data: { count: 1, results: [inquiryRow] } })
  })

  it('lists the inquiries below the map and narrows them to a clicked bubble or card', async () => {
    const wrapper = await mountView()
    expect(api.areaMapInquiries).toHaveBeenLastCalledWith({ activity_type: 'all', page: 1, page_size: 25, ordering: '-first_seen_at' })
    expect(wrapper.find('.area-inquiries').text()).toContain('Verona, DAMAC Hills 2, Dubai')

    // Bubble: the click listener the marker registered. It also scrolls the area list to the card.
    const scrollTo = vi.fn()
    wrapper.find('.area-map__ranking').element.scrollTo = scrollTo
    maps.markers[0].addListener.mock.calls.find(([name]) => name === 'click')[1]()
    await flushPromises()
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ behavior: 'smooth' }))
    expect(api.areaMapInquiries).toHaveBeenLastCalledWith(expect.objectContaining({ area: 1, page: 1 }))
    expect(wrapper.find('.area-inquiries__chip').text()).toContain('DAMAC Hills 2, Dubai')

    // Card of an area that is not on the map still filters the grid.
    await wrapper.findAll('.area-map__ranking li')[1].find('button').trigger('click')
    await flushPromises()
    expect(api.areaMapInquiries).toHaveBeenLastCalledWith(expect.objectContaining({ area: 2 }))

    await wrapper.find('.area-inquiries__chip button').trigger('click')
    await flushPromises()
    expect(api.areaMapInquiries.mock.calls.at(-1)[0]).not.toHaveProperty('area')
    expect(wrapper.find('.area-inquiries__chip').exists()).toBe(false)
  })

  it('collapses and expands the map and Top areas, and remembers it', async () => {
    localStorage.removeItem('chatlens:area-map:panels')
    const wrapper = await mountView()
    const panel = title => wrapper.find(`.area-map__panels [title="${title}"]`)
    const mapShown = () => wrapper.find('.area-map__map-wrap').element.style.display !== 'none'
    const areasShown = () => wrapper.find('.area-map__ranking').element.style.display !== 'none'

    await panel('Collapse the map').trigger('click')
    expect([mapShown(), areasShown()]).toEqual([false, true])
    expect(JSON.parse(localStorage.getItem('chatlens:area-map:panels'))).toEqual({ map: false, areas: true })

    await panel('Expand the map and Top areas').trigger('click')
    expect([mapShown(), areasShown()]).toEqual([true, true])
    await panel('Collapse the map and Top areas').trigger('click')
    expect([mapShown(), areasShown()]).toEqual([false, false])
    expect(wrapper.find('.area-map__layout').element.style.display).toBe('none')
    await panel('Expand Top areas').trigger('click')
    expect([mapShown(), areasShown()]).toEqual([false, true])
    localStorage.removeItem('chatlens:area-map:panels')
  })

  it('goes from an area card to its inquiries in the grid', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const wrapper = await mountView()
    await button(wrapper, 'Go to grid').trigger('click')
    await flushPromises()
    expect(api.areaMapInquiries).toHaveBeenLastCalledWith(expect.objectContaining({ area: 1, page: 1 }))
    expect(scrollIntoView).toHaveBeenCalled()
    expect(scrollIntoView.mock.contexts.at(-1).classList.contains('area-inquiries')).toBe(true)
    delete Element.prototype.scrollIntoView
  })

  it('refreshes from a small icon button', async () => {
    const wrapper = await mountView()
    await wrapper.find('.area-map__refresh').trigger('click')
    await flushPromises()
    expect(api.areaMap).toHaveBeenCalledTimes(2)
  })

  it('opens the original WhatsApp message of a grid row', async () => {
    const wrapper = await mountView()
    await wrapper.find('.area-inquiries [title="View the original WhatsApp message"]').trigger('click')
    expect(whatsapp.viewSource).toHaveBeenCalledWith(inquiryRow)
    await wrapper.find('.area-inquiries [title="Open the original message in the WhatsApp Inbox"]').trigger('click')
    expect(whatsapp.openInInbox).toHaveBeenCalledWith(inquiryRow)
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
    // The totals line and the location backfill live elsewhere now (backfill: AI Instructions).
    expect(wrapper.text()).not.toContain('located in')
    expect(wrapper.text()).not.toContain('Find locations')
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

  it('merges an area written another way into the right one', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.mergeAreas.mockResolvedValue({ data: { ...report(), merged: 1 } })
    const wrapper = await mountView()
    const second = wrapper.findAll('.area-map__ranking li')[1]
    await second.findAll('.area-map__card-actions button').find(b => b.text() === 'Merge...').trigger('click')
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

const status = (overrides = {}) => ({
  opportunities: 12, with_properties: 10, pending: 2, error: 1, locating: 0, location_search_mode: 'web_search',
  error_reasons: [{ error: 'No active agent provider configured.', count: 508 }],
  ...overrides,
})

describe('Location backfill (AI Instructions)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.locationStatus.mockResolvedValue({ data: status() })
  })

  async function mountBackfill() {
    const { default: Backfill } = await import('../components/LocationBackfill.vue')
    const wrapper = mount(Backfill)
    await flushPromises()
    return wrapper
  }

  it('shows what still has no area and why it failed', async () => {
    const wrapper = await mountBackfill()
    expect(wrapper.text()).toContain('3 inquiries have no area yet')
    expect(wrapper.text()).toContain('2 not located yet')
    expect(wrapper.text()).toContain('1 failed')
    expect(wrapper.text()).toContain('with live web search')
    expect(wrapper.text()).toContain('508 × No active agent provider configured.')
  })

  it('queues the location AI for inquiries without an area', async () => {
    api.locateAreas.mockResolvedValue({ data: { ...status({ locating: 3 }), queued: 3 } })
    const wrapper = await mountBackfill()
    await button(wrapper, 'Find locations for 3').trigger('click')
    await flushPromises()
    expect(api.locateAreas).toHaveBeenCalledWith('unlocated')
    expect(wrapper.text()).toContain('3 inquiries queued')
    expect(wrapper.text()).toContain('Locating 3 inquiries...')
  })

  it('asks before re-checking every inquiry', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await mountBackfill()
    await button(wrapper, 'Re-check all').trigger('click')
    expect(confirm.mock.calls[0][0]).toContain('all 10 inquiries with property details')
    expect(api.locateAreas).not.toHaveBeenCalled()
    confirm.mockRestore()
  })
})

describe('Location finding settings', () => {
  it('saves the chosen mode and shows why web search is not available', async () => {
    const choices = [{ value: 'model_knowledge', label: "AI's own market knowledge" }, { value: 'web_search', label: 'AI with live web search (OpenRouter)' }]
    api.getLocationSearch.mockResolvedValue({ data: { mode: 'model_knowledge', choices, web_search_blockers: ['DeepSeek (deepseek)'] } })
    api.setLocationSearch.mockRejectedValue({ response: { status: 400, data: { mode: ['Web search needs OpenRouter models'] } } })
    api.locationStatus.mockResolvedValue({ data: status() })
    const { default: Settings } = await import('../components/LocationSearchSettings.vue')
    const wrapper = mount(Settings)
    await flushPromises()
    expect(wrapper.text()).toContain('Not available yet: the location AI uses DeepSeek (deepseek).')
    await wrapper.find('input[value="web_search"]').setValue(true)
    await button(wrapper, 'Save location finding').trigger('click')
    await flushPromises()
    expect(api.setLocationSearch).toHaveBeenCalledWith('web_search')
    expect(wrapper.find('.location-search__error').text()).toContain('Web search needs OpenRouter models')
    // The backfill is part of the same settings section.
    expect(wrapper.text()).toContain('Inquiries without an area')
  })
})
