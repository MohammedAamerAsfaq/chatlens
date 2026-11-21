"""Conservative, text-based grouping for review selection (not record merging)."""
import hashlib
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher


def normalize_text(text):
    return ' '.join(unicodedata.normalize('NFKC', text or '').casefold().split())


def _numbers(text):
    return tuple(re.findall(r'\d+(?:[.,]\d+)?', text))


def _prefix(text):
    return tuple(re.findall(r'[^\W_]+', text, flags=re.UNICODE)[:3])


class ReviewGroups:
    """Match exact text and conservative near copies to the first representative.

    Near matching requires the same first three word tokens, identical numeric
    sequence, identical word tokens and 97% character similarity. Short messages match exactly only.
    This is a heuristic; membership is not proof of semantic equivalence.
    """
    def __init__(self):
        self.exact = {}
        self.by_prefix = defaultdict(list)
        self.groups = []

    def add(self, text, value):
        normalized = normalize_text(text)
        if not normalized:
            return None
        index = self.exact.get(normalized)
        prefix = _prefix(normalized)
        if index is None and len(normalized) >= 40 and len(prefix) == 3:
            for candidate in self.by_prefix[prefix]:
                representative = self.groups[candidate]['normalized']
                if _numbers(normalized) == _numbers(representative) and re.findall(r'[^\W_]+', normalized) == re.findall(r'[^\W_]+', representative) and SequenceMatcher(None, normalized, representative, autojunk=False).ratio() >= .97:
                    index = candidate
                    break
        if index is None:
            index = len(self.groups)
            self.groups.append({'normalized': normalized, 'id': hashlib.sha256(normalized.encode('utf-8')).hexdigest(), 'members': []})
            self.by_prefix[prefix].append(index)
        self.exact[normalized] = index
        self.groups[index]['members'].append(value)
        return index


def balanced_groups(groups, limit):
    """Interleave AI-predicted classes; strata are sampling hints, not labels."""
    pools = {name: [] for name in ('buy', 'sell', 'non_inquiry', 'uncertain')}
    for group in groups:
        pools[group['pool']].append(group)
    result = []
    while len(result) < limit:
        added = False
        for pool in pools.values():
            if pool and len(result) < limit:
                result.append(pool.pop())
                added = True
        if not added:
            break
    return result
