import { describe, expect, it } from 'vitest'
import { defaultReminderDue, normalizeReminderDefaults } from '../reminderDefaults.js'

describe('ClientPulse reminder defaults', () => {
  it('defaults new reminders to one week at 10:00', () => {
    const now = new Date(2026, 9, 8, 18, 30)

    expect(defaultReminderDue(undefined, now)).toBe('2026-10-15T10:00')
  })

  it('applies configured delay and time and rejects invalid values', () => {
    const now = new Date(2026, 9, 8, 18, 30)

    expect(defaultReminderDue({ delay_days: 2, time: '08:45' }, now)).toBe('2026-10-10T08:45')
    expect(normalizeReminderDefaults({ delay_days: -1, time: '28:90' })).toMatchObject({
      delay_days: 7,
      time: '10:00',
    })
  })
})
