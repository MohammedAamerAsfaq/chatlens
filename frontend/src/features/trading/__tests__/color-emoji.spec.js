import { describe, expect, it } from 'vitest'
import { colorEmojiFor } from '../composables/useColorEmoji'

describe('colorEmojiFor', () => {
  const mapping = { Silver: '⚪', 'Jet Black': '⚫' }

  it('uses the emoji set for the exact catalog Color value', () => {
    expect(colorEmojiFor(mapping, 'Silver')).toBe('⚪')
    expect(colorEmojiFor(mapping, ' Jet Black ')).toBe('⚫')
  })

  it('never guesses an emoji for an unmapped value', () => {
    expect(colorEmojiFor(mapping, 'Glacier')).toBe('')
    expect(colorEmojiFor(mapping, 'silver')).toBe('')
    expect(colorEmojiFor(mapping, '')).toBe('')
    expect(colorEmojiFor({}, 'Silver')).toBe('')
  })
})
