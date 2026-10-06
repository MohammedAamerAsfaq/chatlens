import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  info: vi.fn(),
  convert: vi.fn(),
}))
vi.mock('@/api', () => ({
  chatsApi: { info: api.info },
  clientPulseApi: { convertConversationContact: api.convert },
}))

import ClientPulseChatAction from '../ClientPulseChatAction.vue'

describe('ClientPulseChatAction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().user = {
      permissions: { 'clientpulse.clients.create': 'all' },
    }
    vi.clearAllMocks()
  })

  it('adds an unlinked WhatsApp contact as a lead', async () => {
    api.info.mockResolvedValue({ data: { contact: { id: 42, clientpulse: null } } })
    api.convert.mockResolvedValue({
      data: { profile: { id: 17, lifecycle_stage: 'lead', status: 'active' } },
    })
    const wrapper = mount(ClientPulseChatAction, {
      props: { chatId: 8 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(api.convert).toHaveBeenCalledWith(42, { lifecycle_stage: 'lead' })
    expect(wrapper.text()).toContain('ClientPulse')
    expect(wrapper.text()).toContain('lead')
    expect(wrapper.emitted('converted')[0][0]).toEqual({
      id: 17, lifecycle_stage: 'lead', status: 'active',
    })
  })

  it('shows existing ClientPulse lifecycle and status', async () => {
    api.info.mockResolvedValue({ data: {
      contact: {
        id: 42,
        clientpulse: { id: 17, lifecycle_stage: 'active_customer', status: 'active' },
      },
    } })
    const wrapper = mount(ClientPulseChatAction, {
      props: { chatId: 8 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('active customer')
    expect(wrapper.text()).toContain('active')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
