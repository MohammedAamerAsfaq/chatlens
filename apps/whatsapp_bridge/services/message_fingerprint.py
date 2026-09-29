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
