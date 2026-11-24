"""Sale-or-rent price check for Real Estate extraction.

Many listings and requests never say "for sale" or "for rent"; an amount far below what
that kind of unit sells for in that area is a year's rent. The company chooses where the
typical sale price comes from (RealEstateSettings.price_check_mode):

- model_knowledge: the AI's own knowledge of the market (no extra cost).
- web_search: the AI searches the web for current prices (OpenRouter web search; extra
  cost per message, OpenRouter models only).
- reference_table: the company's own price table (MarketPriceReference rows).
- off: no price check.

The rule is added to the extraction system prompt at call time, so it applies to a
company's saved custom prompt as well as the stock one.
"""

from apps.real_estate.models import MarketPriceReference, RealEstateSettings

WEB_SEARCH_RESULTS = 3
MAX_TABLE_ROWS = 300

_RULE = """Sale price check. Use it only when the message does not plainly say whether the property
is for sale or for rent. Compare any stated amount with the typical sale price for that property
type, size and area {source}. An amount far below that sale price - roughly a tenth of it or
less, the size of a year's rent - is a rent: classify an offered property as leasing_offer and a
wanted property as leasing_inquiry, not selling or buying. An explicit sale or rent statement
always decides over this check. If you cannot establish a typical sale price for that area and
property type{fallback}, do not use this check."""


def price_check_for(company):
    """(text to append to the extraction system prompt, extra agent-call options)."""
    settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
    mode = settings_row.price_check_mode
    if mode == RealEstateSettings.PRICE_CHECK_OFF:
        return '', {}
    if mode == RealEstateSettings.PRICE_CHECK_MODEL:
        return _RULE.format(source='from your own knowledge of that market', fallback=''), {}
    if mode == RealEstateSettings.PRICE_CHECK_WEB:
        rule = _RULE.format(
            source='using the web search results provided with this request (current listings and '
                   'price guides for that area)',
            fallback=' from those results',
        )
        return rule, {'web_search': {'max_results': WEB_SEARCH_RESULTS}}
    if mode == RealEstateSettings.PRICE_CHECK_TABLE:
        rows = list(
            MarketPriceReference.objects.filter(company=company).select_related('property_type')[:MAX_TABLE_ROWS + 1]
        )
        if not rows:
            raise ValueError(
                'The sale price check is set to the company price table, but the table has no prices. '
                'Add prices or choose another price check in AI Instructions.'
            )
        if len(rows) > MAX_TABLE_ROWS:
            raise ValueError(f'The company price table has more than {MAX_TABLE_ROWS} rows; shorten it.')
        rule = _RULE.format(
            source="using the company's sale price table below",
            fallback=' in that table',
        )
        return rule + '\n\nCompany sale price table:\n' + '\n'.join(_table_line(row) for row in rows), {}
    raise ValueError(f'Unknown price check mode: {mode!r}.')


def web_search_blockers(company, key=None):
    """The AI targets of a prompt (extraction by default) that cannot search the web (not
    OpenRouter), as labels."""
    from apps.ai_providers.manager import ai_manager
    from apps.ai_providers.models import AIProviderConfig
    from apps.real_estate.models import RealEstatePromptConfig
    from apps.real_estate.services.prompts import target_prompt_config

    prompt_config = target_prompt_config(company, key or RealEstatePromptConfig.KEY_EXTRACTION)
    if prompt_config and prompt_config.kiwi_router_id:
        configs = [
            member.provider_config
            for member in prompt_config.kiwi_router.members.filter(is_enabled=True).select_related('provider_config')
        ]
    elif prompt_config and prompt_config.agent_config_id:
        configs = [prompt_config.agent_config]
    else:
        configs = [ai_manager.active_config('agent', company=company)]
    return [
        f'{config.display_name} ({config.provider})' for config in configs
        if config and config.provider != AIProviderConfig.PROVIDER_OPENROUTER
    ]


def _table_line(row):
    parts = [row.location]
    parts.append(row.property_type.name if row.property_type_id else 'any property type')
    if row.bedrooms is not None:
        bedrooms = int(row.bedrooms) if row.bedrooms == row.bedrooms.to_integral_value() else row.bedrooms
        parts.append('studio' if bedrooms == 0 else f'{bedrooms} bedrooms')
    parts.append(f'{row.currency} {row.sale_price_min:,.0f} to {row.sale_price_max:,.0f}')
    if row.notes:
        parts.append(row.notes)
    return '- ' + ' | '.join(parts)
