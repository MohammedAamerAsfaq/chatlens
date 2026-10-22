import { describe, expect, it } from 'vitest'

import { resolveRouterBase } from './base'

describe('resolveRouterBase', () => {
  it('keeps application routes at the site root by default', () => {
    expect(resolveRouterBase()).toBe('/')
  })

  it('allows an explicit application mount path', () => {
    expect(resolveRouterBase('/chatlens/')).toBe('/chatlens/')
  })
})
