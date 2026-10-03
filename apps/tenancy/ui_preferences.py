DEFAULT_INSPINIA_CONFIG = {
    'skin': 'default',
    'color_scheme': 'light',
    'topbar_color': 'light',
    'sidenav_color': 'dark',
    'sidenav_size': 'default',
    'layout_width': 'fluid',
    'direction': 'ltr',
    'layout_position': 'fixed',
    'orientation': 'vertical',
    'sidebar_user': True,
}

INSPINIA_OPTIONS = {
    'skin': [
        'default', 'minimal', 'modern', 'material', 'saas', 'flat',
        'galaxy', 'luxe', 'retro', 'neon', 'pixel',
    ],
    'color_scheme': ['light', 'dark', 'system'],
    'topbar_color': ['light', 'dark', 'gray', 'gradient'],
    'sidenav_color': ['light', 'dark', 'gray', 'gradient', 'image'],
    'sidenav_size': [
        'default', 'compact', 'condensed', 'on_hover',
        'on_hover_active', 'offcanvas',
    ],
    'layout_width': ['fluid', 'boxed'],
    'direction': ['ltr', 'rtl'],
    'layout_position': ['fixed', 'scrollable'],
    'orientation': ['vertical', 'horizontal'],
    'sidebar_user': [True, False],
}


def normalize_inspinia_config(value, *, strict=False):
    if value is None:
        return DEFAULT_INSPINIA_CONFIG.copy()
    if not isinstance(value, dict):
        if strict:
            raise ValueError('inspinia_config must be an object.')
        return DEFAULT_INSPINIA_CONFIG.copy()

    if strict:
        unknown = sorted(set(value) - set(INSPINIA_OPTIONS))
        if unknown:
            raise ValueError(f'Unknown Inspinia settings: {", ".join(unknown)}.')

    result = DEFAULT_INSPINIA_CONFIG.copy()
    for key, allowed in INSPINIA_OPTIONS.items():
        candidate = value.get(key, result[key])
        if candidate not in allowed:
            if strict:
                choices = ', '.join(str(item) for item in allowed)
                raise ValueError(f'{key} must be one of: {choices}.')
            continue
        result[key] = candidate
    return result
