export const DEFAULT_THEME = 'chatlens'

export const themes = Object.freeze({
  chatlens: {
    key: 'chatlens',
    name: 'ChatLens',
    description: 'The original compact horizontal workspace.',
  },
  inspinia: {
    key: 'inspinia',
    name: 'Inspinia',
    description: 'A sidebar workspace for dense operational applications.',
  },
})

export function normalizeTheme(value) {
  return themes[value]?.key || DEFAULT_THEME
}
