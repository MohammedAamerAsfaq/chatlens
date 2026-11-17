// How inquiry lines are written in the replies we construct (WA Client, WA ChatLens,
// ChatLens send, Ask Price).

// A matched catalog product is trusted for pricing and prefill unless the AI marked the
// line a near (not exact) match. Whether product_id is the right product is the AI's
// call (match_type exact/near/null); we don't re-check it with our own string compare.
// A line with no match_type (older inquiries, before the field existed) is trusted.
export function isReliableMatch(p, match) {
  if (!match) return false
  return p.match_type !== 'near'
}

// Product.name in the catalog never includes the brand (brand is a separate field), but
// canonical_name from the AI sometimes does — either bracketed "[Apple] iPhone..." or a
// bare "Apple iPhone..." prefix. Purely cosmetic cleanup for outgoing WhatsApp text.
export function stripBrandPrefix(name, brand) {
  let s = (name || '').replace(/^\[[^\]]*\]\s*/, '')
  if (brand) {
    s = s.replace(new RegExp('^' + brand.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s+', 'i'), '')
  }
  return s.trim()
}

// The item text used in every reply we construct from an inquiry. A trusted match uses our
// inventory's item description (Product.name), so customers see our naming; a near match or
// an unmatched line keeps the sender's own wording, since the catalog row may not be the
// item they asked about.
export function replyItemName(p, match) {
  const name = isReliableMatch(p, match) ? match.name : (p.canonical_name || match?.name)
  return stripBrandPrefix(name, match?.brand)
}
