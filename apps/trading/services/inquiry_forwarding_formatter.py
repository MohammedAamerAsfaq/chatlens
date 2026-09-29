import re
from urllib.parse import quote


def product_name(row):
    return str(row.get('canonical_name') or row.get('raw_text') or '').strip()


def sender_link(source, prefill_text=''):
    raw = getattr(source.contact, 'phone_number', '') if source.contact_id else ''
    raw = raw or source.sender_number or ''
    digits = re.sub(r'\D', '', raw)
    if not digits:
        return ''
    link = f'https://wa.me/{digits}'
    return f'{link}?text={quote(prefill_text, safe="")}' if prefill_text else link


def build_forwarding_message(rule, inquiry, source):
    label = 'WTB' if inquiry.inquiry_type == 'buy' else 'WTS'
    sections = []
    if rule.include_original_message:
        text = (source.message_text or '').strip()
        if not text:
            return ''
        sections.append(text)

    products = [row for row in inquiry.products if isinstance(row, dict) and product_name(row)]
    if rule.include_summary and (inquiry.summary or '').strip():
        sections.append(f'Summary:\n{inquiry.summary.strip()}')

    suggestions = _stock_suggestions(inquiry, products) if rule.include_stock_suggestions else []
    if suggestions:
        sections.append('\n'.join(['In-stock exact matches:', *suggestions]))
    if rule.include_sender_link:
        reply_label = 'WTS' if inquiry.inquiry_type == 'buy' else 'WTB'
        prefill = _product_prefill(reply_label, products) if rule.prefill_sender_link_products else ''
        sections.append(f'Direct chat: {sender_link(source, prefill)}')
    footer = [f'{label} inquiry']
    if rule.include_inquiry_id:
        footer.append(f'Inquiry ID: #{inquiry.pk}')
    sections.append('\n'.join(footer))
    return '\n\n'.join(sections)


def _product_prefill(label, products):
    lines = [label]
    for product in products:
        details = [product_name(product)]
        quantity = product.get('quantity')
        if quantity is not None:
            details.append(f'Qty {quantity}')
        price = product.get('price')
        if price is not None:
            currency = str(product.get('currency') or '').strip()
            details.append(f'{currency} {price}'.strip())
        lines.append(f'- {" | ".join(details)}')
    return '\n'.join(lines)


def _stock_suggestions(inquiry, products):
    from apps.trading.models import Product

    ids = [row.get('product_id') for row in products if row.get('match_type') == 'exact']
    inventory = Product.objects.filter(company=inquiry.company, pk__in=ids, is_active=True, qty__gt=0)
    result = []
    for product in inventory:
        price = f' | {product.currency} {product.sale_price}' if product.sale_price is not None else ''
        result.append(f'- {product.name} | Qty {product.qty}{price}')
    return result
