import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ClientPulseConversionCard from '../ClientPulseConversionCard.vue'
import { useAuthStore } from '@/stores/auth'
import { clientPulseApi } from '@/api'

vi.mock('@/api', () => ({
  clientPulseApi: { convertConversationContact: vi.fn() },
}))

describe('ClientPulse conversation conversion', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().user = {
      permissions: {
        'clientpulse.clients.create': 'all',
        'clientpulse.clients.update': 'all',
      },
    }
    vi.clearAllMocks()
  })

  it('creates a profile with the selected lifecycle stage', async () => {
    clientPulseApi.convertConversationContact.mockResolvedValue({
      data: {
        created: true,
        changed: false,
        profile: { id: 17, lifecycle_stage: 'prospect' },
      },
    })
    const wrapper = mount(ClientPulseConversionCard, {
      props: { contactId: 42 },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    await wrapper.get('select').setValue('prospect')
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(wrapper.emitted('converted')).toBeTruthy())

    expect(clientPulseApi.convertConversationContact).toHaveBeenCalledWith(42, {
      lifecycle_stage: 'prospect',
    })
    expect(wrapper.emitted('converted')[0][0]).toEqual({ id: 17, lifecycle_stage: 'prospect' })
    expect(wrapper.text()).toContain('ClientPulse profile created.')
  })

  it('shows the existing profile and update action', () => {
    const wrapper = mount(ClientPulseConversionCard, {
      props: { contactId: 42, profile: { id: 17, lifecycle_stage: 'active_customer' } },
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })

    expect(wrapper.get('select').element.value).toBe('active_customer')
    expect(wrapper.text()).toContain('Open profile')
    expect(wrapper.text()).toContain('Update lifecycle')
  })
})
