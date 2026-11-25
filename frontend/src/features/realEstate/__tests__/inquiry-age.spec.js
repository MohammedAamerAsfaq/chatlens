import { describe, expect, it } from 'vitest'
import { ageLabel, daysOld } from '@/features/realEstate/boardOptions'

describe('inquiry age', () => {
  const now = new Date(2026, 10, 25, 9, 0)

  it('counts calendar days, not 24-hour periods', () => {
    expect(daysOld(new Date(2026, 10, 25, 0, 5), now)).toBe(0)
    expect(daysOld(new Date(2026, 10, 24, 23, 59), now)).toBe(1)
    expect(daysOld(new Date(2026, 9, 29, 11, 13), now)).toBe(27)
  })

  it('labels the age and leaves missing dates blank', () => {
    expect(ageLabel(new Date(2026, 10, 25, 8, 0), now)).toBe('Today')
    expect(ageLabel(new Date(2026, 10, 24, 8, 0), now)).toBe('1 day old')
    expect(ageLabel(new Date(2026, 10, 20, 8, 0).toISOString(), now)).toBe('5 days old')
    expect(ageLabel(null, now)).toBe('')
    expect(ageLabel('not a date', now)).toBe('')
  })
})
