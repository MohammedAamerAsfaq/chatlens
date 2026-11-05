"""Deterministic fingerprints for exact cross-chat message deduplication."""
import hashlib
import re
import unicodedata


def normalize_message_text(value: str) -> str:
    """Normalize presentation differences without changing meaningful content."""
    text = unicodedata.normalize('NFKC', value or '').casefold()
    lines = (' '.join(line.split()) for line in text.splitlines())
    return '\n'.join(line for line in lines if line).strip()


def message_text_fingerprint(value: str) -> str:
    normalized = normalize_message_text(value)
    if not normalized:
        return ''
    # Ignore WhatsApp emphasis markers so formatting-only reposts still match.
    normalized = re.sub(r'(?<!\w)[*_~]|[*_~](?!\w)', '', normalized)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def message_dedup_key(direction: str, contact_wa_id: str, fingerprint: str) -> str:
    """In-house dedup key: same sender + identical normalized text.

    Shared by the duplicate-broadcast skip and inquiry merging. Only inbound messages
    carry one — the sender of an outbound message is ourselves, not the chat contact.
    """
    if direction != 'inbound' or not contact_wa_id or not fingerprint:
        return ''
    return f'{contact_wa_id}:{fingerprint}'
