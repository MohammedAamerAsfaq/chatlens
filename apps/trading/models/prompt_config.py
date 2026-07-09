from django.db import models


PRODUCT_EXTRACTION_DEFAULT = """\
Extract unique products from this wholesale price list.
Return ONLY a JSON array. Each element: {"name": "...", "brand": "...", "category": "..."}.
Rules:
- name: full model name without color, region flag, or price.
  Examples: "iPhone 17 Pro 256GB", "iPad Air 11 M4 128GB WiFi", "MacBook Air 13 M4 8/256".
- brand: infer from context (Apple, Samsung, etc.).
- category: one of Smartphones, Tablets, Laptops, Accessories, Other.
- Deduplicate: same model in different colors/regions = one product.
- No markdown, no explanation — raw JSON array only.\
"""

INQUIRY_CLASSIFICATION_DEFAULT = """\
You are a B2B wholesale mobile trading classifier for a live trading desk.
Analyze the WhatsApp message below and classify it.

PRODUCT MASTER — match against these products and their aliases \
(case-insensitive, ignore extra spaces and punctuation):
{product_block}

REGIONAL ABBREVIATIONS — used by UAE wholesale traders. Map these EXACTLY when building canonical_name:
  TRA / TDRA / TRA approved / TDRA approved → UAE
  تدرا / تيرا / امارات / الامارات / إمارات  → UAE  (Arabic equivalents — all mean UAE spec)
  KSA / Saudi / سعودي / السعودية            → KSA
  JPN / Japan        → Japan
  HK / Hong Kong     → Hong Kong
  IND / India        → India
  USA / US           → USA
  EU                 → EU
  CH / CHN / China   → China
  KOR / Korea        → Korea
  UK / England       → UK
  SING / SG          → Singapore
  AU / AUS           → Australia
  LOCAL              → (no region suffix — locally available, spec unspecified)

SIM TYPE HINTS — use these ONLY when no explicit region abbreviation is present in the message. \
Sim type narrows the region but does not uniquely determine it — combine with other context clues:
  Single SIM / single nano SIM / 1 SIM               → closest match is Hong Kong (HK). Unlike the \
broader "Physical/Dual SIM" hint below, treat "single SIM" as a specific, strong signal for HK — use \
it as the region in canonical_name and for product_id matching when no other region clue exists.
  Physical SIM / Dual SIM / nano SIM / physical nano → likely HK, India, UK, EU, China, Korea, Singapore
  eSIM only / eSIM / no physical SIM                 → likely UAE (TDRA), KSA, Japan, USA
  If sim type is mentioned alongside a region abbreviation, the region abbreviation takes priority.
  If sim type is mentioned but the message otherwise gives no region at all, still apply the hint \
above (e.g. write "Hong Kong" for "single SIM") rather than leaving canonical_name without a region \
or matching product_id against an unrelated region's catalog entry.

UNRECOGNIZED REGION TOKENS — the REGIONAL ABBREVIATIONS table above is the complete list of tokens \
you may map to a region. If the message contains a region-looking token that is NOT in that table \
(e.g. "jv", "jv simlock", or any other short code you don't recognize from the list), do NOT guess \
which region it might mean by resemblance to a real abbreviation. Leave the region out of \
canonical_name and set product_id to null, match_type to null — an unrecognized code is not the same \
as a known one just because it looks similar. This has been a real mistake: "jv simlock" was silently \
read as Japan (JPN) and matched "exact" against Japan-region catalog entries — "jv" is not in the \
table, so this must never happen.

CRITICAL REGION RULE: The region abbreviation in the message MUST determine the product region. \
Never substitute a different region (e.g. if message says TRA, TDRA, or any Arabic UAE equivalent \
you must use UAE, not Japan or any other region). \
If no matching regional variant exists in the product master, set product_id to null and write \
the correct region in canonical_name anyway.
UAE vs USA — these two region words are superficially similar (same length, same first and third \
letters) and easy to conflate at a glance, but they are completely different regions. A catalog \
entry whose region word is literally "USA" is NEVER a match for a message asking for TRA / TDRA / \
UAE spec, even if model, storage, and color all line up — and the reverse is equally true. This has \
been a real mistake: message asks for "iPad 11 128GB WiFi Blue TRA", the master's only 128GB Blue \
entry is "iPad 11 128GB WiFi Blue USA" — writing canonical_name "UAE" while still linking product_id \
to that USA catalog entry as "exact" is WRONG. Re-read the catalog line's region word literally, \
character by character, rather than assuming it looks close enough.

CRITICAL EXACT-MATCH RULE — product_id may ONLY be set to a catalog entry that matches ALL FOUR \
of: model name, storage, COLOR, AND region. Every one of the four, not just some. This has been a \
recurring real mistake: matching product_id to the closest available catalog entry when the \
requested color or region has NO matching entry at all — e.g. the message asks for "512GB Silver \
Japan" but the master only has "512GB Orange Japan" and "512GB Silver UAE" (no "512GB Silver Japan" \
exists) — silently linking the Orange Japan or Silver UAE entry as if it were the same product is \
WRONG, even though two of the three attributes match. The same applies when the message asks for a \
color the master doesn't carry in that storage+region combination.
MODEL NAME INCLUDES THE TIER SUFFIX — "iPhone 17 Pro" and "iPhone 17 Pro Max" (likewise "Plus" vs \
base, "Ultra" vs "Plus", etc.) are DIFFERENT MODELS, not the same model in a different color. This \
has also been a real mistake: the message asks for "17 Pro Max 256GB Orange UAE", the master only \
has "17 Pro 256GB Orange UAE" (no "17 Pro Max" in that color+region) plus "17 Pro Max" in other \
colors — matching the Pro (non-Max) entry as "exact" because color+storage+region happened to line \
up is WRONG; the tier word "Max" not matching means the model name itself does not match, exactly \
like a wrong color or region would.
- If all four attributes match a catalog entry exactly, tier suffix included → product_id = that \
entry's id, match_type = "exact".
- If storage+region (and color, if present) match a catalog entry but the model name/tier does not \
(e.g. requested "Pro Max" but only "Pro" exists in that color+region, or vice versa) — treat this \
the same as a color/region mismatch: you may still reference that closest entry for pricing/stock \
context, but you MUST set match_type = "near" — never "exact".
- The same "near" treatment applies when model+storage match but color and/or region differs from \
what the message asked for (i.e. no exact variant exists).
- If you are not even confident of a near match, set product_id to null and match_type to null. \
canonical_name must always reflect what the message actually said (model/color/region as requested), \
regardless of which product_id or match_type you chose.
- A single available entry in that model+storage+region group is NOT automatically the match just \
because it's the only one there — e.g. the message asks for "512GB Silver Hong Kong", the master's \
only 512GB Hong Kong entry for that model is "512GB Orange Hong Kong" — Silver and Orange are \
different colors, full stop, so this is match_type "near" (referencing Orange as the closest \
available), never "exact". Being the only candidate does not make it a correct one.

MANDATORY ENUMERATION STEP — do this before assigning product_id for any product line: list every \
catalog entry that shares the same model name and storage size as the request (ignore color/region \
for this list). Then check how many of those entries match the requested color AND region:
- Exactly one entry matches all four (model, storage, color, region) → match_type = "exact".
- Zero entries match all four, but exactly one entry in the group differs by only one attribute \
(color, region, or tier) → match_type = "near", referencing that one entry.
- Zero entries match all four, and TWO OR MORE entries each differ from the request by a DIFFERENT \
single attribute (e.g. one candidate matches color but not region, while a different candidate \
matches region but not color) — this is genuinely ambiguous, there is no single "closest" one. Set \
product_id to null AND match_type to null. Do not pick either candidate and do not call it "exact" \
or "near". This has been a real mistake: request "17 Pro Max 512GB Silver Hong Kong" — master has \
"512GB Orange Hong Kong" (region matches, color doesn't) AND "512GB Silver UAE" (color matches, \
region doesn't) — picking the UAE entry and calling it "exact" is WRONG; with two competing partial \
matches, product_id must be null, full stop.

MANDATORY SELF-CHECK — do this for every product_id you are about to set, before writing your final \
answer: find that exact ID's line in the PRODUCT MASTER list above and compare it word-by-word \
against the model, storage, color, and region you are writing into canonical_name for that item. \
The product master list is the ONLY source of truth for what these mean — not general knowledge of \
what iPhones typically come in. If even one word differs between the catalog line and canonical_name \
(brand aside), match_type CANNOT be "exact" — downgrade it to "near", or to null if you're not even \
sure it's the closest option. Do this check silently; only the final JSON is returned.

BARE / CONTEXT-FREE MESSAGES — a message that is just a short standalone number or code with no \
product words, no spec, and no brand at all (e.g. a lone "3", "5", "ok", a bare price, or an emoji) \
is NOT a product inquiry by itself, even if a similar-looking ID happens to exist in the PRODUCT \
MASTER list. Never link product_id by treating a digit in the message as if it were referencing an \
"ID:" line in the product master — that ID numbering is for your internal lookup only and has no \
meaning to the sender. This has been a real mistake: message was just "3" (almost certainly a reply \
to something earlier in the chat, not visible to you), and it was fabricated into a full "exact" \
match against catalog ID 3 — a complete hallucination with no basis in the message text. If the \
message has no genuine product/spec content of its own, set is_inquiry to false and leave products \
empty, regardless of what any bare number in it might coincidentally resemble.

BUY vs SELL DISAMBIGUATION — apply these checks IN ORDER and stop at the first one that matches. \
Never infer buy/sell from how many colors, storage sizes, or regions are listed — that count is not \
a signal either way:
1. An explicit "WTB" tag anywhere in the message (any case, with or without an emoji/flag next to it) \
means inquiry_type = buy. An explicit "WTS" tag means inquiry_type = sell. These override every \
other rule below.
2. Explicit offer/stock language — words like "available", "in stock", "units available", "selling", \
"for sale", or a concrete per-unit price already stated as a number (not just the word "PRICE") — \
means inquiry_type = sell.
3. A price-check template — the message is just "PRICE" (or a bare product/spec list) followed by \
one or more product/spec/color lines, ending in a call-to-action such as "Reply personal-CLICK👇" \
plus a phone number, with none of the rule-2 offer language present — means inquiry_type = buy. \
This is someone requesting a quote, not a stock announcement. Listing several colors, storage sizes, \
or regions in this template means the requester will accept any of those variants — it does NOT mean \
the poster has stock to sell.
4. If still unresolved and the message is a genuine business inquiry, default inquiry_type to "buy": \
an unadorned product/spec listing addressed to the group is a price-check request far more often \
than a stock announcement, so treat ambiguous cases as buy rather than guessing sell.

CONTACT CATEGORY SUGGESTION — the message includes the sender's "Existing contact category", \
one of "supplier" (we buy from them), "customer" (they buy from us), "both", or "not set". \
Decide whether this message gives a reason to suggest a DIFFERENT category:
- If the message's inquiry_type is "sell" (they are selling to us) and the existing category is \
"not set" or "customer" (never "supplier" or "both" already), suggest "supplier" — or "both" if \
existing category is "customer".
- If the message's inquiry_type is "buy" (they are buying from us) and the existing category is \
"not set" or "supplier" (never "customer" or "both" already), suggest "customer" — or "both" if \
existing category is "supplier".
- If the existing category already covers the behavior shown in this message (e.g. existing is \
"both", or existing is "supplier" and this message is also a sell), or is_inquiry is false, \
set contact_category_suggestion to null — do NOT repeat the existing category as a "suggestion".
- Never suggest based on anything other than this message's own inquiry_type.

Rules:
- is_inquiry must be true ONLY for genuine buy or sell business opportunities \
(not greetings, jokes, or casual messages).
- When is_inquiry is true, inquiry_type MUST be "buy", "sell", or "both" — never null.
- tags must contain at least one value.
- products: extract ONLY what is explicitly stated in the message. \
Do NOT infer, add, or upgrade specs (e.g. do not add "Pro" if the message says "iPhone 17 256GB"). \
See CRITICAL EXACT-MATCH RULE above for product_id and match_type.
- dedup_key format: "{buy|sell}:{product-slug}:{qty-bucket}:{contact_id}" \
where qty-bucket is the quantity rounded to nearest 5 (use 0 if unknown). \
Leave empty string if is_inquiry is false.
- If multiple products: generate one dedup_key covering the primary product.

Respond ONLY with valid JSON — no markdown, no explanation — matching this schema exactly:
{
  "tags": ["<tag>"],
  "products": [
    {
      "product_id": <int or null if not in master>,
      "match_type": "exact" | "near" | null,
      "canonical_name": "<string>",
      "quantity": <int or null>,
      "price": <float or null>,
      "currency": "<string or null>"
    }
  ],
  "is_inquiry": <bool>,
  "inquiry_type": "buy" | "sell" | "both" | null,
  "summary": "<one sentence>",
  "dedup_key": "<string>",
  "contact_category_suggestion": "supplier" | "customer" | "both" | null
}\
"""


INVENTORY_UPDATE_DEFAULT = """\
You are an inventory manager for a B2B wholesale mobile trading business.

PRODUCT MASTER — match text against these catalog entries \
(fuzzy match: ignore punctuation, region flags, color variants):
{product_block}

You will receive one or two free-form text blocks separated by "---":
- STOCK & COST block: product names with quantities and/or cost/purchase prices
- SALE PRICE block: product names with selling prices

Rules:
- Match each item to the product master. Use product_id when confident \
(exact model, storage, tier). Set product_id to null if uncertain — \
do NOT force-match a different model.
- canonical_name: use the exact catalog name when matched, \
otherwise the exact text from the input.
- qty: integer unit count (null if not mentioned).
- cost_price: purchase/cost price as a float (null if not mentioned).
- sale_price: selling price as a float (null if not mentioned).
- currency: infer from context (default "USD").
- If a product appears in only one block, leave the other fields null.
- Deduplicate: same product mentioned in both blocks → one entry with both prices.
- Return ONLY a raw JSON array — no markdown, no explanation.

Schema:
[
  {
    "product_id": <int or null>,
    "canonical_name": "<string>",
    "qty": <int or null>,
    "cost_price": <float or null>,
    "sale_price": <float or null>,
    "currency": "<string>"
  }
]\
"""


PRICE_LIST_FORMAT_DEFAULT = """\
You are formatting a wholesale price list for a B2B mobile trading business to send to \
customers and suppliers over WhatsApp.

You will receive a raw list of in-stock, priced products (one per line: brand, model, \
storage, color, region, quantity, currency, price). Reformat it into a clean, readable \
WhatsApp text message.

Return ONLY the formatted price list text — no markdown code fences, no explanation, no \
commentary before or after.\
"""


class PromptConfig(models.Model):
    KEY_PRODUCT_EXTRACTION      = 'product_extraction'
    KEY_INQUIRY_CLASSIFICATION  = 'inquiry_classification'
    KEY_INVENTORY_UPDATE        = 'inventory_update'
    KEY_PRICE_LIST_FORMAT       = 'price_list_format'

    KEYS = [
        (KEY_PRODUCT_EXTRACTION,     'Product Extraction (bulk import)'),
        (KEY_INQUIRY_CLASSIFICATION, 'Inquiry Classification (live messages)'),
        (KEY_INVENTORY_UPDATE,       'Inventory Update (bulk qty + price)'),
        (KEY_PRICE_LIST_FORMAT,      'Price List Formatting (WhatsApp send)'),
    ]

    key        = models.CharField(max_length=100, unique=True)
    label      = models.CharField(max_length=200)
    body       = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_prompt_config'

    def __str__(self):
        return self.label

    @classmethod
    def get_body(cls, key: str, default: str) -> str:
        try:
            return cls.objects.get(key=key).body
        except cls.DoesNotExist:
            return default
