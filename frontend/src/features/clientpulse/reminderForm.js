import { defaultReminderDue } from './reminderDefaults.js'

// The reminder editor's form state and API payload, shared by the Reminders page and the Inbox.

export function blankReminderForm({ defaults, owners = [], profileId = null } = {}) {
  return {
    profile_id: profileId,
    assigned_to_id: owners.length === 1 ? owners[0].id : null,
    linked_from_id: null,
    title: '', description: '', due_at: defaultReminderDue(defaults),
    priority: 'normal', recurrence_type: 'none', interval_days: 1,
  }
}

// A follow-up continues the thread of `item`: same client, assignee and priority.
export function followUpFields(item) {
  return {
    profile_id: item.profile.id,
    assigned_to_id: item.assigned_to?.id || null,
    linked_from_id: item.id,
    priority: item.priority || 'normal',
  }
}

export function reminderPayload(form, { timezone, editing = false }) {
  const payload = {
    profile_id: form.profile_id,
    assigned_to_id: form.assigned_to_id || null,
    title: form.title,
    description: form.description,
    due_at: new Date(form.due_at).toISOString(),
    timezone,
    priority: form.priority,
    recurrence_type: form.recurrence_type,
    recurrence_rule: form.recurrence_type === 'custom' ? { interval_days: Number(form.interval_days) } : {},
  }
  if (!editing && form.linked_from_id) payload.linked_from_id = form.linked_from_id
  return payload
}
