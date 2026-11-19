import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CampaignListsView from '../CampaignListsView.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(),
  candidates: vi.fn(), addMembers: vi.fn(), removeMembers: vi.fn(),
}))
const router = vi.hoisted(() => ({ replace: vi.fn() }))
vi.mock('@/api', () => ({ campaignListsApi: api }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => router }))

const detail = (members = []) => ({
  id: 4, kind: 'contacts', name: 'VIP buyers', description: '', created_by: 'aamer',
  member_count: members.length, hidden_member_count: 0, members,
})
const ali = { id: 31, contact_id: 11, name: 'Ali', detail: '971511111111', account_name: 'Sales', usable: true }

const button = (wrapper, text) => wrapper.findAll('button').find(item => item.text() === text || item.attributes('aria-label') === text)

describe('CampaignListsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    useAuthStore().user = {
      current_company: { id: 1 },
      permissions: { 'campaigns.campaigns.view': 'all', 'campaigns.audiences.manage': 'all' },
    }
    api.list.mockResolvedValue({ data: [{ id: 4, kind: 'contacts', name: 'VIP buyers', member_count: 0 }] })
    api.get.mockResolvedValue({ data: detail() })
  })

  it('creates a contact list', async () => {
    api.list.mockResolvedValue({ data: [] })
    api.create.mockResolvedValue({ data: detail() })
    const wrapper = mount(CampaignListsView)
    await flushPromises()
    await wrapper.find('form.lists-create input').setValue('VIP buyers')
    await wrapper.find('form.lists-create').trigger('submit')
    await flushPromises()
    expect(api.create).toHaveBeenCalledWith({ kind: 'contacts', name: 'VIP buyers' })
    expect(wrapper.find('.lists-index').text()).toContain('VIP buyers')
  })

  it('searches contacts and adds one to the open list', async () => {
    api.candidates.mockResolvedValue({ data: { count: 1, page: 1, page_size: 25, results: [{ id: 11, name: 'Ali', detail: '971511111111', account_name: 'Sales' }] } })
    api.addMembers.mockResolvedValue({ data: { added: 1, skipped: 0, list: detail([ali]) } })
    const wrapper = mount(CampaignListsView)
    await flushPromises()
    await wrapper.find('.lists-index button').trigger('click')
    await flushPromises()

    await wrapper.find('form.lists-search input').setValue('ali')
    await wrapper.find('form.lists-search').trigger('submit')
    await flushPromises()
    expect(api.candidates).toHaveBeenCalledWith(4, { search: 'ali', page: 1 })

    await button(wrapper, 'Add Ali').trigger('click')
    await flushPromises()
    expect(api.addMembers).toHaveBeenCalledWith(4, { ids: [11] })
    expect(wrapper.find('.lists-members').text()).toContain('Ali')
    expect(wrapper.find('.lists-index').text()).toContain('1 contact')
  })

  it('flags members that campaigns will skip', async () => {
    api.get.mockResolvedValue({ data: detail([{ ...ali, usable: false }]) })
    const wrapper = mount(CampaignListsView)
    await flushPromises()
    await wrapper.find('.lists-index button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.lists-members').text()).toContain('Skipped')
    expect(wrapper.find('.lists-members').text()).toContain('will be skipped when this list is added to a campaign')
  })

  it('lets members without list permission look but not change anything', async () => {
    useAuthStore().user.permissions = { 'campaigns.campaigns.view': 'all' }
    api.get.mockResolvedValue({ data: detail([ali]) })
    const wrapper = mount(CampaignListsView)
    await flushPromises()
    expect(wrapper.find('form.lists-create').exists()).toBe(false)
    await wrapper.find('.lists-index button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.lists-add').exists()).toBe(false)
    expect(button(wrapper, 'Remove Ali')).toBeUndefined()
    expect(button(wrapper, 'Delete')).toBeUndefined()
  })
})
