export const CAMPAIGN_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const MAX_CAMPAIGN_IMAGE_BYTES = 10 * 1024 * 1024
export const MAX_CAPTION_LENGTH = 1024
export const MAX_TEXT_LENGTH = 10000
// "Send anyway" lifts the limits above, but never past the longest message WhatsApp carries.
export const MAX_OVERRIDE_LENGTH = 65536

export function campaignCharacterCount(message) {
  return [...String(message || '')].length
}

export function campaignMessageLimit(hasImage) {
  return hasImage ? MAX_CAPTION_LENGTH : MAX_TEXT_LENGTH
}

export function campaignImageError(file) {
  if (!CAMPAIGN_IMAGE_TYPES.includes(file?.type) || file.size > MAX_CAMPAIGN_IMAGE_BYTES) {
    return 'Select a JPEG, PNG, or WebP image no larger than 10 MB.'
  }
  return ''
}

// A direct-message campaign sends its typed text; when it also has products (e.g. from a
// saved product list), their formatted lines follow after a blank line.
export function directMessageWithProducts(text, productLines) {
  const message = text || ''
  return productLines.length ? [message, '', ...productLines].join('\n') : message
}
