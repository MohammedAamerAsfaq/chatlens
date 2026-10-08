import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
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
