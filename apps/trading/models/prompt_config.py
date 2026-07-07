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
  Physical SIM / Dual SIM / nano SIM / physical nano → likely HK, India, UK, EU, China, Korea, Singapore
  eSIM only / eSIM / no physical SIM                 → likely UAE (TDRA), KSA, Japan, USA
  If sim type is mentioned alongside a region abbreviation, the region abbreviation takes priority.

CRITICAL REGION RULE: The region abbreviation in the message MUST determine the product region. \
Never substitute a different region (e.g. if message says TRA, TDRA, or any Arabic UAE equivalent \
you must use UAE, not Japan or any other region). \
If no matching regional variant exists in the product master, set product_id to null and write \
the correct region in canonical_name anyway.

CRITICAL EXACT-MATCH RULE — product_id may ONLY be set to a catalog entry that matches ALL FOUR \
of: model name, storage, COLOR, AND region. Every one of the four, not just some. This has been a \
recurring real mistake: matching product_id to the closest available catalog entry when the \
requested color or region has NO matching entry at all — e.g. the message asks for "512GB Silver \
Japan" but the master only has "512GB Orange Japan" and "512GB Silver UAE" (no "512GB Silver Japan" \
exists) — silently linking the Orange Japan or Silver UAE entry as if it were the same product is \
WRONG, even though two of the three attributes match. The same applies when the message asks for a \
color the master doesn't carry in that storage+region combination.
- If all four attributes match a catalog entry exactly → product_id = that entry's id, match_type = "exact".
- If the model+storage match a catalog entry but its color and/or region differs from what the \
message asked for (i.e. no exact variant exists) → you may still reference that closest entry \
for pricing/stock context, but you MUST set match_type = "near" — never "exact" — so the desk \
knows this is not the color/region the customer actually asked for.
- If you are not even confident of a near match, set product_id to null and match_type to null. \
canonical_name must always reflect what the message actually said (color/region as requested), \
regardless of which product_id or match_type you chose.

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


class PromptConfig(models.Model):
    KEY_PRODUCT_EXTRACTION      = 'product_extraction'
    KEY_INQUIRY_CLASSIFICATION  = 'inquiry_classification'
    KEY_INVENTORY_UPDATE        = 'inventory_update'

    KEYS = [
        (KEY_PRODUCT_EXTRACTION,     'Product Extraction (bulk import)'),
        (KEY_INQUIRY_CLASSIFICATION, 'Inquiry Classification (live messages)'),
        (KEY_INVENTORY_UPDATE,       'Inventory Update (bulk qty + price)'),
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
