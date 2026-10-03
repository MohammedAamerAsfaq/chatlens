export const DEFAULT_INSPINIA_CONFIG = Object.freeze({
  skin: 'default',
  color_scheme: 'light',
  topbar_color: 'light',
  sidenav_color: 'dark',
  sidenav_size: 'default',
  layout_width: 'fluid',
  direction: 'ltr',
  layout_position: 'fixed',
  orientation: 'vertical',
  sidebar_user: true,
})

export function normalizeInspiniaConfig(value = {}) {
  return { ...DEFAULT_INSPINIA_CONFIG, ...(value || {}) }
}

export function inspiniaClasses(config) {
  const value = normalizeInspiniaConfig(config)
  return [
    `skin-${value.skin}`,
    `scheme-${value.color_scheme}`,
    `topbar-${value.topbar_color}`,
    `sidenav-${value.sidenav_color}`,
    `sidenav-size-${value.sidenav_size.replaceAll('_', '-')}`,
    `layout-width-${value.layout_width}`,
    `layout-position-${value.layout_position}`,
    `orientation-${value.orientation}`,
    { 'sidebar-user-hidden': !value.sidebar_user },
  ]
}
