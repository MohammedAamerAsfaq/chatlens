import { describe, expect, it } from 'vitest'

// The Font Awesome icon font (CSS) is not loaded; icons render only through the
// FontAwesomeIcon component. An <i class="fa-..."> tag shows nothing at all.
const sources = import.meta.glob('/src/**/*.vue', { query: '?raw', import: 'default', eager: true })

describe('icons', () => {
  it('uses FontAwesomeIcon instead of icon-font classes', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(50)
    const offenders = Object.entries(sources)
      .filter(([, text]) => /<i\s+class="fa-(solid|regular|brands)/.test(text))
      .map(([path]) => path)
    expect(offenders).toEqual([])
  })
})
