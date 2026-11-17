import { describe, expect, it } from 'vitest'
import { replyItemName } from '../composables/replyItems'

const product = { name: 'iPhone 17 Pro Max 256GB Deep Blue', brand: 'Apple' }

describe('reply item text', () => {
  it('uses our inventory item description for a trusted match', () => {
    const line = { canonical_name: '[Apple] 17 pro max 256 blue', match_type: 'exact' }
    expect(replyItemName(line, product)).toBe('iPhone 17 Pro Max 256GB Deep Blue')
  })

  it('treats a line without match_type (older inquiries) as a trusted match', () => {
    expect(replyItemName({ canonical_name: '17pm 256 blue' }, product)).toBe('iPhone 17 Pro Max 256GB Deep Blue')
  })

  it('keeps the sender wording for a near match, minus the brand prefix', () => {
    const line = { canonical_name: 'Apple iPhone 17 Pro 256GB Blue', match_type: 'near' }
    expect(replyItemName(line, product)).toBe('iPhone 17 Pro 256GB Blue')
  })

  it('keeps the sender wording when nothing matched', () => {
    expect(replyItemName({ canonical_name: '[Samsung] S26 Ultra 512' }, null)).toBe('S26 Ultra 512')
  })
})
