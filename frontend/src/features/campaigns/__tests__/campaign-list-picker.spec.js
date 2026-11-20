import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignListPicker from '../components/CampaignListPicker.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('@/api', () => ({ campaignListsApi: api }))

const RouterLinkStub = { props: ['to'], template: '<a><slot /></a>' }

function mountPicker(props = {}) {
  return mount(CampaignListPicker, {
    props: { kind: 'contacts', apply: vi.fn(), ...props },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

describe('CampaignListPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    useAuthStore().user = {
      current_company: { id: 1 },
      permissions: { 'campaigns.campaigns.update': 'all', 'campaigns.audiences.manage': 'all' },
    }
    api.list.mockResolvedValue({ data: [{ id: 4, name: 'VIP buyers', member_count: 12 }] })
  })

  it('adds the chosen saved list to the campaign and reports what happened', async () => {
    const apply = vi.fn().mockResolvedValue({ data: { added: 9, skipped: 2, unavailable: 1, offer: { id: 7 } } })
    const wrapper = mountPicker({ apply })
    await flushPromises()
    expect(api.list).toHaveBeenCalledWith({ kind: 'contacts' })
    expect(wrapper.find('select').text()).toContain('VIP buyers (12)')

    await wrapper.find('select').setValue(4)
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(apply).toHaveBeenCalledWith(4)
    expect(wrapper.emitted('applied')[0][0].offer).toEqual({ id: 7 })
    expect(wrapper.text()).toContain('9 added · 2 already in this campaign · 1 unavailable')
    expect(wrapper.text()).toContain('Manage lists')
  })

  it('shows the server reason when a list cannot be added', async () => {
    const apply = vi.fn().mockRejectedValue({ response: { data: { list_id: ['This campaign sends to groups; choose a group list.'] } } })
    const wrapper = mountPicker({ apply })
    await flushPromises()
    await wrapper.find('select').setValue(4)
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toBe('This campaign sends to groups; choose a group list.')
  })

  it('adds a saved product list on its own', async () => {
    api.list.mockResolvedValue({ data: [{ id: 9, name: 'A15 parts', member_count: 3 }] })
    const apply = vi.fn().mockResolvedValue({ data: { added: 2, skipped: 0, unavailable: 1, offer: { id: 7 } } })
    const wrapper = mountPicker({ kind: 'products', apply })
    await flushPromises()
    expect(api.list).toHaveBeenCalledWith({ kind: 'products' })
    expect(wrapper.find('select').text()).toContain('Choose a product list...')

    await wrapper.find('select').setValue(9)
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(apply).toHaveBeenCalledWith(9)
    expect(wrapper.text()).toContain('2 added · 1 unavailable (inactive)')
  })

  it('is hidden from members who cannot change campaigns', async () => {
    useAuthStore().user.permissions = { 'campaigns.campaigns.view': 'all' }
    const wrapper = mountPicker()
    await flushPromises()
    expect(wrapper.find('.campaign-list-picker').exists()).toBe(false)
    expect(api.list).not.toHaveBeenCalled()
  })
})
