import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { describe, expect, it } from 'vitest'
import ReminderEditorModal from '../ReminderEditorModal.vue'

describe('ReminderEditorModal', () => {
  it('identifies a linked follow-up and locks it to the same client', async () => {
    const host = document.createElement('div')
    host.id = 'ui-teleport-host'
    document.body.append(host)
    const form = {
      profile_id: 2, assigned_to_id: 4, linked_from_id: 11,
      title: '', description: '', due_at: '2026-10-09T10:00',
      priority: 'normal', recurrence_type: 'none', interval_days: 1,
    }
    const wrapper = mount(ReminderEditorModal, {
      props: {
        open: true, form,
        linkedFrom: { id: 11, title: 'Previous customer action' },
        clients: [{ id: 2, display_name: 'Example Client' }],
        owners: [{ id: 4, username: 'owner' }],
      },
    })
    await nextTick(); await nextTick()

    expect(host.textContent).toContain('Create linked follow-up')
    expect(host.textContent).toContain('Previous customer action')
    expect(host.querySelector('select')?.disabled).toBe(true)

    wrapper.unmount(); host.remove()
  })
})

describe('ReminderEditorModal actions', () => {
  it('fills the title from a preset action and shows which one the title matches', async () => {
    const host = document.createElement('div')
    host.id = 'ui-teleport-host'
    document.body.append(host)
    const form = reactive({
      profile_id: 2, assigned_to_id: '', title: 'Send price list', description: '',
      due_at: '2026-10-09T10:00', priority: 'normal', recurrence_type: 'none', interval_days: 1,
    })
    const phrases = [{ id: 1, text: 'Sent Hi' }, { id: 2, text: 'Send price list' }]
    const wrapper = mount(ReminderEditorModal, {
      props: { open: true, form, phrases, clients: [{ id: 2, display_name: 'Example Client' }] },
    })
    await nextTick(); await nextTick()

    const action = [...host.querySelectorAll('select')].find(select => select.textContent.includes('Sent Hi'))
    expect(action.value).toBe('2')

    action.value = '1'
    action.dispatchEvent(new Event('change'))
    await nextTick()
    expect(form.title).toBe('Sent Hi')

    form.title = 'Call about the late shipment'
    await nextTick()
    expect(action.value).toBe('')

    wrapper.unmount(); host.remove()
  })
})
