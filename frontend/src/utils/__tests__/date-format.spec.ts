import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatTime } from '../dateFormat'

const fourthNovember = new Date(2026, 10, 4, 10, 5, 9)

describe('dateFormat', () => {
  it('writes the day first whatever the browser locale is', () => {
    expect(formatDate(fourthNovember)).toBe('04/11/2026')
    expect(formatDateTime(fourthNovember)).toBe('04/11/2026, 10:05 AM')
    expect(formatDateTime(fourthNovember, { seconds: true })).toBe('04/11/2026, 10:05:09 AM')
  })

  it('uses a 12-hour clock', () => {
    expect(formatTime(new Date(2026, 0, 1, 0, 7))).toBe('12:07 AM')
    expect(formatTime(new Date(2026, 0, 1, 12, 0))).toBe('12:00 PM')
    expect(formatTime(new Date(2026, 0, 1, 23, 59))).toBe('11:59 PM')
  })

  it('returns the empty value for missing or invalid dates', () => {
    expect(formatDate(null)).toBe('')
    expect(formatDate('', '-')).toBe('-')
    expect(formatDateTime('not a date', { empty: '—' })).toBe('—')
  })
})
