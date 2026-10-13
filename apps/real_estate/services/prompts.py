from apps.real_estate.models import RealEstatePromptConfig


DEFAULT_GATE_PROMPT = """You are the strict first gate for a real-estate CRM.
Decide whether the message concerns buying, selling, renting, or offering a property.
Return JSON only: {"decision":"real_estate|not_real_estate|needs_review"}.
Use needs_review when property intent is plausible but unclear. Do not infer real-estate
intent from greetings, generic business messages, or unrelated product trading."""

DEFAULT_EXTRACTION_PROMPT = """Classify one real-estate message into exactly one decision:
buying, selling, leasing_inquiry, leasing_offer, not_real_estate, or needs_review.
Buying means seeking a property to purchase. Selling means offering a property for sale.
Leasing inquiry means seeking a property to rent. Leasing offer means offering a property
for rent. Use needs_review when the real-estate intent exists but its lane is ambiguous.
Return JSON only with this schema:
{
  "decision": "...",
  "summary": "concise factual summary",
  "confidence": 0.0,
  "property": {
    "market_scope": "local|regional|international",
    "ownership_eligibility": "locals_only|gcc_only|all",
    "tenure_type": "freehold|long_lease|lease_99_year|",
    "property_type": "",
    "locations": [],
    "bedrooms_min": null,
    "bedrooms_max": null,
    "bathrooms_min": null,
    "bathrooms_max": null,
    "area_min": null,
    "area_max": null,
    "area_unit": "",
    "budget_min": null,
    "budget_max": null,
    "currency": "",
    "furnishing": "",
    "timeframe": "",
    "amenities": [],
    "free_form_constraints": "",
    "attributes": {}
  }
}
Use attributes only for facts relevant to the selected property type, such as view,
parking, balconies, maid's room, AC type, district cooling company, management
company, master developer, facilities, roof height, decor status, floor, unit mix,
gross floor area, use, or FAR. Do not invent missing values."""


def configured_prompt(company, key):
    config = RealEstatePromptConfig.get_for_company(company, key)
    if config and config.body.strip():
        return config.body.strip(), config
    default = DEFAULT_GATE_PROMPT if key == RealEstatePromptConfig.KEY_GATE else DEFAULT_EXTRACTION_PROMPT
    return default, config


def message_prompt(message):
    return (
        f'Chat type: {message.chat.chat_type}\n'
        f'Sender: {message.sender_number or "unknown"}\n'
        f'Message:\n{message.message_text}'
    )
