import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatReminders from '../ChatReminders.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  reminders: vi.fn(), completeReminder: vi.fn(), createReminder: vi.fn(),
  options: vi.fn(), reminderPhrases: vi.fn(),
}))
vi.mock('@/api', () => ({ clientPulseApi: api }))

const overdue = {
  id: 31, title: 'Followup on New Order', status: 'due', priority: 'high',
  due_at: '2026-11-03T06:00:00Z', snoozed_until: null,
  profile: { id: 6 }, assigned_to: { id: 4, username: 'celluspare' },
}
const byLabel = (wrapper, label) => wrapper.findAll('button').find(item => item.attributes('aria-label') === label)

describe('ChatReminders', () => {
  let host
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
    host = document.createElement('div'); host.id = 'ui-teleport-host'; document.body.append(host)
    setActivePinia(createPinia())
    useAuthStore().user = {
      current_company: { id: 7 },
      permissions: { 'clientpulse.reminders.view': 'all', 'clientpulse.reminders.manage': 'all' },
    }
    api.reminders.mockResolvedValue({ data: { results: [overdue], count: 1 } })
    api.completeReminder.mockResolvedValue({ data: {} })
    api.createReminder.mockResolvedValue({ data: {} })
    api.options.mockResolvedValue({ data: { owners: [{ id: 4, username: 'celluspare' }], reminder_defaults: {} } })
    api.reminderPhrases.mockResolvedValue({ data: [] })
  })

  it("lists the client's open reminders and flags the overdue ones", async () => {
    const wrapper = mount(ChatReminders, { props: { profile: { id: 6 }, clientName: 'edwin multimedia' } })
    await flushPromises()
    expect(api.reminders).toHaveBeenCalledWith({ window: 'open', profile_id: 6, page_size: 50 })
    expect(byLabel(wrapper, 'Client reminders').text()).toBe('1')
    expect(byLabel(wrapper, 'Client reminders').classes()).toContain('has-overdue')

    await byLabel(wrapper, 'Client reminders').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Followup on New Order')
    expect(wrapper.text()).toContain('Overdue')
    wrapper.unmount()
  })

  it('completes a reminder and creates its linked follow-up for the same client', async () => {
    const wrapper = mount(ChatReminders, { props: { profile: { id: 6 }, clientName: 'edwin multimedia' } })
    await flushPromises()
    await byLabel(wrapper, 'Client reminders').trigger('click')
    await flushPromises()
    await byLabel(wrapper, 'Complete + follow-up').trigger('click')
    await flushPromises()

    expect(api.completeReminder).toHaveBeenCalledWith(31)
    expect(host.textContent).toContain('Create linked follow-up')
    host.querySelector('input[placeholder="What needs follow-up?"]').value = 'Send price list'
    host.querySelector('input[placeholder="What needs follow-up?"]').dispatchEvent(new Event('input'))
    host.querySelector('#reminder-editor-form').dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(api.createReminder).toHaveBeenCalledWith(expect.objectContaining({
      profile_id: 6, linked_from_id: 31, assigned_to_id: 4, priority: 'high', title: 'Send price list',
    }))
    wrapper.unmount()
  })
})
