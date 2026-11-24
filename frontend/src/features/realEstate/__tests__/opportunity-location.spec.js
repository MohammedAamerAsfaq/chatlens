import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OpportunityCard from '../components/OpportunityCard.vue'
import OpportunityLocationDialog from '../components/OpportunityLocationDialog.vue'

const api = vi.hoisted(() => ({ locateOpportunity: vi.fn(), setOpportunityLocation: vi.fn() }))
vi.mock('@/api', () => ({ realEstateApi: api }))

const lane = { key: 'buying', tone: 'buying' }
const located = {
  id: 11, sequence: 1, title: '', locations: ['Verona'], geo_status: 'located', geo_source: 'ai',
  geo_area: 'DAMAC Hills 2', geo_sub_area: 'Verona', geo_city: 'Dubai', geo_confidence: '0.9000',
  geo_basis: 'Verona is a cluster in DAMAC Hills 2', geo_error: '',
  geo_position: { status: 'placed', latitude: 24.98, longitude: 55.39, matched_label: 'DAMAC Hills 2', error: '' },
}
const unlocated = { id: 12, sequence: 1, title: '', locations: [], geo_status: 'pending', geo_source: '', geo_area: '', geo_sub_area: '', geo_city: '', geo_basis: '', geo_error: '', geo_position: null }
const opportunity = item => ({ id: 7, activity_type: 'buying', status: 'new', items: item ? [item] : [] })

describe('Inquiry card location button', () => {
  it('shows a map icon with the place when the inquiry has a location', async () => {
    const wrapper = mount(OpportunityCard, { props: { opportunity: opportunity(located), lane } })
    const button = wrapper.find('.opportunity-card__map')
    expect(button.attributes('title')).toBe('Location: Verona, DAMAC Hills 2, Dubai')
    expect(button.classes()).not.toContain('opportunity-card__map--none')
    await button.trigger('click')
    expect(wrapper.emitted('location')[0][0].id).toBe(7)
  })

  it('offers to add a location when there is none, and nothing without property details', () => {
    const wrapper = mount(OpportunityCard, { props: { opportunity: opportunity(unlocated), lane } })
    expect(wrapper.find('.opportunity-card__map--none').attributes('aria-label')).toBe('Add location')
    const empty = mount(OpportunityCard, { props: { opportunity: opportunity(null), lane } })
    expect(empty.find('.opportunity-card__map').exists()).toBe(false)
  })
})

describe('Location dialog', () => {
  let host
  beforeEach(() => {
    vi.clearAllMocks()
    host = document.createElement('div')
    host.id = 'ui-teleport-host'
    document.body.append(host)
  })
  afterEach(() => host.remove())

  const open = item => mount(OpportunityLocationDialog, { props: { open: true, opportunity: opportunity(item) }, attachTo: document.body })
  const button = text => [...document.querySelectorAll('#ui-teleport-host button')].find(b => b.textContent.includes(text))

  it('shows the place, why, and a Google Maps link', () => {
    open(located)
    const text = host.textContent
    expect(text).toContain('Verona, DAMAC Hills 2, Dubai')
    expect(text).toContain('Found by the location AI · 90% sure')
    expect(text).toContain('Verona is a cluster in DAMAC Hills 2')
    expect(host.querySelector('a').getAttribute('href')).toBe('https://www.google.com/maps/search/?api=1&query=24.98%2C55.39')
  })

  it('finds the location with AI and passes the updated inquiry up', async () => {
    const updated = opportunity(located)
    api.locateOpportunity.mockResolvedValue({ data: updated })
    const wrapper = open(unlocated)
    expect(host.textContent).toContain('Not located yet')
    button('Find with AI').click()
    await flushPromises()
    expect(api.locateOpportunity).toHaveBeenCalledWith(7)
    expect(wrapper.emitted('updated')[0][0]).toBe(updated)
  })

  it('sets a location by hand', async () => {
    api.setOpportunityLocation.mockResolvedValue({ data: opportunity(located) })
    const wrapper = open(unlocated)
    button('Add location').click()
    await flushPromises()
    const input = label => host.querySelector(`input[aria-label="${label}"]`)
    for (const [label, value] of [['Area', 'DAMAC Hills 2'], ['Building, cluster or project', 'Verona'], ['City', 'Dubai']]) {
      input(label).value = value
      input(label).dispatchEvent(new Event('input'))
    }
    host.querySelector('form').dispatchEvent(new Event('submit'))
    await flushPromises()
    expect(api.setOpportunityLocation).toHaveBeenCalledWith(7, { item: 12, action: 'set', area: 'DAMAC Hills 2', sub_area: 'Verona', city: 'Dubai' })
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('clears a location after asking, and shows a refusal', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.setOpportunityLocation.mockRejectedValue({ response: { status: 400, data: { item: ['Choose a property of this inquiry.'] } } })
    open(located)
    button('Clear location').click()
    await flushPromises()
    expect(confirm.mock.calls[0][0]).toContain('will not set it again on its own')
    expect(api.setOpportunityLocation).toHaveBeenCalledWith(7, { item: 11, action: 'clear' })
    expect(host.querySelector('[role="alert"]').textContent).toContain('Choose a property of this inquiry.')
    confirm.mockRestore()
  })
})
