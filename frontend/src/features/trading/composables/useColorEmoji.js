import { ref } from 'vue'
import { tradingApi } from '@/api'

// The company's emoji for each catalog Color value (AI Instructions → Color emoji).
// Looked up by the exact stored value; an unmapped colour gets no emoji.
export function colorEmojiFor(mapping, colorName) {
  if (!colorName) return ''
  return mapping?.[colorName.trim()] || ''
}

export function useColorEmoji() {
  const mapping = ref({})
  const loadError = ref('')

  async function load() {
    try {
      const { data } = await tradingApi.getColorEmojiSettings()
      mapping.value = data.emoji
      loadError.value = ''
    } catch (exc) {
      loadError.value = exc.response?.data?.detail || exc.message || 'Unable to load the Color emoji settings.'
    }
  }

  return {
    mapping,
    loadError,
    load,
    colorEmoji: (colorName) => colorEmojiFor(mapping.value, colorName),
  }
}
