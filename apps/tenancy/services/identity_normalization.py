import re


_NON_DIGIT = re.compile(r'\D+')
_JID_DEVICE = re.compile(r'^([^:@]+):\d+(@.+)$')


def normalize_identity(identity_type, value):
    """Return a stable comparison key without guessing missing country codes."""
    raw = str(value or '').strip()
    if not raw:
        return ''
    if identity_type == 'email':
        return raw.casefold()
    if identity_type == 'phone':
        return _NON_DIGIT.sub('', raw)
    if identity_type == 'whatsapp_jid':
        return normalize_whatsapp_jid(raw)
    if identity_type in {'telegram_handle', 'discord_handle'}:
        return raw.lstrip('@').casefold()
    return ' '.join(raw.casefold().split())


def normalize_whatsapp_jid(value):
    jid = str(value or '').strip().casefold()
    return _JID_DEVICE.sub(r'\1\2', jid)


def phone_from_whatsapp_jid(value):
    jid = normalize_whatsapp_jid(value)
    local, separator, domain = jid.partition('@')
    if not separator or domain not in {'s.whatsapp.net', 'c.us'}:
        return ''
    return _NON_DIGIT.sub('', local)
