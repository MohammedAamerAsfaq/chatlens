import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import KiwiRouterView from '../KiwiRouterView.vue'

const api = vi.hoisted(() => ({
  routers: { list: vi.fn(), update: vi.fn(), create: vi.fn(), delete: vi.fn() },
  providers: { list: vi.fn(), fetchMetadata: vi.fn() },
}))
vi.mock('@/api', () => ({ kiwiRoutersApi: api.routers, aiProvidersApi: api.providers }))

const member = (id, priority, extra = {}) => ({
  id, provider_config: 1, priority, is_enabled: true, rpm_limit: 5, tpm_limit: 50000, max_concurrency: null,
  input_cost_per_million: null, output_cost_per_million: null, request_timeout_seconds: 180, metadata_source: 'incomplete', ...extra,
})

describe('KiwiRouter page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.routers.list.mockResolvedValue({ data: [{
      id: 3, name: 'Kiwi Router 2', capability: 'agent', strategy: 'ordered_capacity_fill', is_active: true,
      members: [member(10, 1, { metadata_source: 'provider_published' }), member(11, 2)],
    }] })
    api.providers.list.mockResolvedValue({ data: [{ id: 1, capability: 'agent', display_name: 'OpenRouter', model: 'openai/gpt-oss-20b' }] })
    api.routers.update.mockImplementation((id, data) => Promise.resolve({ data: JSON.parse(JSON.stringify(data)) }))
  })

  it('lays each agent out as a card and saves reordered, cleared limits', async () => {
    const wrapper = mount(KiwiRouterView)
    await flushPromises()

    expect(wrapper.findAll('.kiwi__member')).toHaveLength(2)
    expect(wrapper.text()).toContain('10 RPM')
    expect(wrapper.text()).toContain('1 / 2')

    const second = wrapper.findAll('.kiwi__member')[1]
    await second.find('[aria-label="Move up"]').trigger('click')
    const first = wrapper.findAll('.kiwi__member')[0]
    const tpm = first.findAll('.kiwi__limits input')[1]
    await tpm.setValue('')

    await wrapper.findAll('button').find(b => b.text() === 'Save changes').trigger('click')
    await flushPromises()
    const [, payload] = api.routers.update.mock.calls[0]
    expect(payload.members.map(m => [m.id, m.priority])).toEqual([[11, 1], [10, 2]])
    expect(payload.members[0].tpm_limit).toBeNull()
    expect(wrapper.find('.ui-notice').text()).toBe('Router saved.')
  })

  it('clears the saved message once something else happens', async () => {
    const wrapper = mount(KiwiRouterView)
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Save changes').trigger('click')
    await flushPromises()
    api.routers.update.mockRejectedValueOnce({ response: { data: { name: ['Too long.'] } } })
    await wrapper.findAll('button').find(b => b.text() === 'Save changes').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.ui-notice')).toHaveLength(1)
    expect(wrapper.find('.ui-notice').text()).toBe('name: Too long.')
  })
})
