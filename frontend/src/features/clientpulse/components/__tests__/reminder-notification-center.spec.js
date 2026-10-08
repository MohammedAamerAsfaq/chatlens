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

vi.mock('@/api', () => ({ clientPulseApi: api }))
vi.mock('vue-router', () => ({ useRouter: () => router }))
vi.mock('@/features/clientpulse/reminderSound', () => ({
  playReminderSound: vi.fn().mockResolvedValue(true),
  primeReminderAudio: vi.fn().mockResolvedValue(true),
}))

describe('ReminderNotificationCenter', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="ui-teleport-host"></div>'
    sessionStorage.clear()
    setActivePinia(createPinia())
    useAuthStore().user = {
      current_company: { id: 7 },
      permissions: {
        'clientpulse.reminders.view': 'all',
        'clientpulse.reminders.manage': 'all',
      },
    }
    api.notifications.mockResolvedValue({ data: [{
      id: 12, read_at: null,
      reminder: {
        id: 3, title: 'Call buyer', priority: 'high', due_at: '2026-10-07T12:00:00Z',
        profile: { id: 9, display_name: 'Acme Buyer' },
      },
    }] })
    api.readNotification.mockResolvedValue({ data: { status: 'read' } })
    api.dismissNotification.mockResolvedValue({ data: { status: 'dismissed' } })
    api.notificationPreferences.mockResolvedValue({ data: {
      reminders_enabled: true, reminder_popup_enabled: true,
    } })
  })

  it('shows due reminders globally and marks them read', async () => {
    const wrapper = mount(ReminderNotificationCenter)
    await flushPromises()
    expect(document.body.textContent).toContain('Call buyer')
    expect(document.body.textContent).toContain('Acme Buyer')

    const markRead = [...document.body.querySelectorAll('button')]
      .find(button => button.textContent === 'Mark read')
    markRead.click()
    await flushPromises()
    expect(api.readNotification).toHaveBeenCalledWith(12)
    expect(document.body.textContent).not.toContain('Call buyer')
    wrapper.unmount()
  })
})
