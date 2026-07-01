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

Rules:
- is_inquiry must be true ONLY for genuine buy or sell business opportunities \
(not greetings, jokes, or casual messages).
- When is_inquiry is true, inquiry_type MUST be "buy", "sell", or "both" — never null.
- tags must contain at least one value.
- products: extract ONLY what is explicitly stated in the message. \
Do NOT infer, add, or upgrade specs (e.g. do not add "Pro" if the message says "iPhone 17 256GB"). \
Use the product_id from the master catalog ONLY when you are certain it is the exact same model \
(matching name, storage, and tier). If uncertain, set product_id to null and use the exact \
product description from the message as canonical_name.
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
      "canonical_name": "<string>",
      "quantity": <int or null>,
      "price": <float or null>,
      "currency": "<string or null>"
    }
  ],
  "is_inquiry": <bool>,
  "inquiry_type": "buy" | "sell" | "both" | null,
  "summary": "<one sentence>",
  "dedup_key": "<string>"
}\
"""


class PromptConfig(models.Model):
    KEY_PRODUCT_EXTRACTION      = 'product_extraction'
    KEY_INQUIRY_CLASSIFICATION  = 'inquiry_classification'

    KEYS = [
        (KEY_PRODUCT_EXTRACTION,     'Product Extraction (bulk import)'),
        (KEY_INQUIRY_CLASSIFICATION, 'Inquiry Classification (live messages)'),
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
