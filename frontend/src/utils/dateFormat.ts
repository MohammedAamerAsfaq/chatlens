// One date format for the whole app: dd/MM/yyyy, with 12-hour time where a time is shown.
// Built by hand rather than with toLocaleString(), whose order follows each browser's locale
// (a US-English browser showed 4 November as 11/4/2026).

type DateInput = string | number | Date | null | undefined

const pad = (value: number) => String(value).padStart(2, '0')

function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === '') return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** dd/MM/yyyy, or `empty` when there is no valid date. */
export function formatDate(value: DateInput, empty = ''): string {
  const date = toDate(value)
  if (!date) return empty
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`
}

/** hh:mm AM/PM (hh:mm:ss AM/PM with `seconds`), or `empty` when there is no valid date. */
export function formatTime(value: DateInput, { seconds = false, empty = '' } = {}): string {
  const date = toDate(value)
  if (!date) return empty
  const hours = date.getHours()
  const clock = `${pad(hours % 12 || 12)}:${pad(date.getMinutes())}${seconds ? `:${pad(date.getSeconds())}` : ''}`
  return `${clock} ${hours < 12 ? 'AM' : 'PM'}`
}

/** dd/MM/yyyy, hh:mm AM/PM (with seconds when asked), or `empty` when there is no valid date. */
export function formatDateTime(value: DateInput, { seconds = false, empty = '' } = {}): string {
  const date = toDate(value)
  if (!date) return empty
  return `${formatDate(date)}, ${formatTime(date, { seconds })}`
}
