import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ReminderNotificationCenter from '../ReminderNotificationCenter.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  notifications: vi.fn(), readNotification: vi.fn(), dismissNotification: vi.fn(),
  snoozeReminder: vi.fn(), notificationPreferences: vi.fn(),
}))
const router = vi.hoisted(() => ({ push: vi.fn() }))
const inbox = vi.hoisted(() => ({ openClientInbox: vi.fn() }))

vi.mock('@/api', () => ({ clientPulseApi: api }))
vi.mock('vue-router', () => ({ useRouter: () => router }))
vi.mock('@/features/clientpulse/reminderSound', () => ({
  playReminderSound: vi.fn().mockResolvedValue(true),
  primeReminderAudio: vi.fn().mockResolvedValue(true),
}))
vi.mock('@/features/clientpulse/composables/useClientInboxNavigation', async () => {
  const { ref } = await import('vue')
  return { useClientInboxNavigation: () => ({ openingContactId: ref(null), openClientInbox: inbox.openClientInbox }) }
})

const button = (wrapper, label) => wrapper.findAll('button').find(item => (item.attributes('aria-label') || '').startsWith(label))

describe('ReminderNotificationCenter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    setActivePinia(createPinia())
    useAuthStore().user = {
      current_company: { id: 7 },
      permissions: {
        'clientpulse.reminders.view': 'all',
        'clientpulse.reminders.manage': 'all',
        'conversations.chats.view': 'all',
      },
    }
    api.notifications.mockResolvedValue({ data: [{
      id: 12, read_at: null,
      reminder: {
        id: 3, title: 'Call buyer', priority: 'high', due_at: '2026-10-07T12:00:00Z',
        profile: {
          id: 9, display_name: 'Acme Buyer',
          communication_accounts: [{ id: 4, whatsapp_contact_id: 55, name: 'Sales line' }],
        },
      },
    }] })
    api.readNotification.mockResolvedValue({ data: { status: 'read' } })
    api.dismissNotification.mockResolvedValue({ data: { status: 'dismissed' } })
    api.notificationPreferences.mockResolvedValue({ data: { reminders_enabled: true } })
    inbox.openClientInbox.mockResolvedValue()
  })

  it('collects due reminders under the bell instead of showing them on the page', async () => {
    const wrapper = mount(ReminderNotificationCenter)
    await flushPromises()
    expect(wrapper.text()).not.toContain('Call buyer')
    expect(wrapper.find('button[aria-label="Reminders"] b').text()).toBe('1')

    await wrapper.find('button[aria-label="Reminders"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Call buyer')
    expect(wrapper.text()).toContain('Acme Buyer')

    await button(wrapper, 'Mark read').trigger('click')
    await flushPromises()
    expect(api.readNotification).toHaveBeenCalledWith(12)
    expect(wrapper.text()).toContain('Call buyer')
    expect(wrapper.find('button[aria-label="Reminders"] b').exists()).toBe(false)
    wrapper.unmount()
  })

  it('opens the client conversation in WhatsApp Inbox', async () => {
    const wrapper = mount(ReminderNotificationCenter)
    await flushPromises()
    await wrapper.find('button[aria-label="Reminders"]').trigger('click')
    await flushPromises()

    await button(wrapper, 'WhatsApp').trigger('click')
    await flushPromises()
    expect(api.readNotification).toHaveBeenCalledWith(12)
    expect(inbox.openClientInbox).toHaveBeenCalledWith(4, 55)
    expect(wrapper.find('.reminder-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows no WhatsApp button to members who cannot view chats', async () => {
    delete useAuthStore().user.permissions['conversations.chats.view']
    const wrapper = mount(ReminderNotificationCenter)
    await flushPromises()
    await wrapper.find('button[aria-label="Reminders"]').trigger('click')
    await flushPromises()
    expect(button(wrapper, 'WhatsApp')).toBeUndefined()
    wrapper.unmount()
  })
})
