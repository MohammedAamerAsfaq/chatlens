export const FALLBACK_REMINDER_DEFAULTS = Object.freeze({
  delay_days: 7,
  time: '10:00',
  timezone: 'Asia/Dubai',
})

export function normalizeReminderDefaults(value = {}) {
  const delay = Number(value.delay_days)
  return {
    delay_days: Number.isInteger(delay) && delay >= 0 ? delay : FALLBACK_REMINDER_DEFAULTS.delay_days,
    time: /^([01]\d|2[0-3]):[0-5]\d$/.test(value.time || '') ? value.time : FALLBACK_REMINDER_DEFAULTS.time,
    timezone: value.timezone || FALLBACK_REMINDER_DEFAULTS.timezone,
  }
}

export function defaultReminderDue(value, now = new Date()) {
  const defaults = normalizeReminderDefaults(value)
  const due = new Date(now)
  const [hours, minutes] = defaults.time.split(':').map(Number)
  due.setDate(due.getDate() + defaults.delay_days)
  due.setHours(hours, minutes, 0, 0)
  return new Date(due.getTime() - due.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
