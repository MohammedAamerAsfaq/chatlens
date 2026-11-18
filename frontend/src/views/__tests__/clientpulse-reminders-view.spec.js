import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ClientPulseRemindersView from '../ClientPulseRemindersView.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  reminders: vi.fn(), dashboard: vi.fn(), notifications: vi.fn(),
  clients: vi.fn(), options: vi.fn(), reminderPhrases: vi.fn(),
}))
const inbox = vi.hoisted(() => ({ openClientInbox: vi.fn() }))

vi.mock('@/api', () => ({ clientPulseApi: api }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/features/clientpulse/composables/useClientInboxNavigation', async () => {
  const { ref } = await import('vue')
  return { useClientInboxNavigation: () => ({ openingContactId: ref(null), openClientInbox: inbox.openClientInbox }) }
})

const mountView = () => mount(ClientPulseRemindersView, {
  global: { stubs: { RouterLink: RouterLinkStub, UiSelect: true }, directives: { uiDataTable: {} } },
})

describe('ClientPulseRemindersView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    useAuthStore().user = {
      current_company: { id: 7 },
      permissions: { 'clientpulse.reminders.view': 'all', 'clientpulse.reminders.manage': 'all', 'conversations.chats.view': 'all' },
    }
    api.reminders.mockResolvedValue({ data: { count: 1, results: [{
      id: 3, title: 'Follow up on New Order', status: 'due', due_at: '2026-11-04T06:00:00Z', priority: 'normal',
      recurrence_type: 'none', profile: {
        id: 9, display_name: 'Acme Buyer',
        communication_accounts: [{ id: 4, whatsapp_contact_id: 55, name: 'Sales line' }],
      },
    }] } })
    api.dashboard.mockResolvedValue({ data: {} })
    api.notifications.mockResolvedValue({ data: [] })
    api.clients.mockResolvedValue({ data: { results: [] } })
    api.options.mockResolvedValue({ data: { owners: [], reminder_defaults: {} } })
    api.reminderPhrases.mockResolvedValue({ data: [] })
    inbox.openClientInbox.mockResolvedValue()
  })

  it('opens the client WhatsApp conversation from a reminder row', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('button[aria-label="WhatsApp: Sales line"]').trigger('click')
    expect(inbox.openClientInbox).toHaveBeenCalledWith(4, 55)
  })

  it('shows no WhatsApp button to members who cannot view chats', async () => {
    delete useAuthStore().user.permissions['conversations.chats.view']
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('button[aria-label^="WhatsApp"]').exists()).toBe(false)
  })
})
