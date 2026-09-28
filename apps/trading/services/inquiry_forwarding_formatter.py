import re


def product_name(row):
    return str(row.get('canonical_name') or row.get('raw_text') or '').strip()


def sender_link(source):
    raw = getattr(source.contact, 'phone_number', '') if source.contact_id else ''
    raw = raw or source.sender_number or ''
    digits = re.sub(r'\D', '', raw)
    return f'https://wa.me/{digits}' if digits else ''


def build_forwarding_message(rule, inquiry, source):
    label = 'WTB' if inquiry.inquiry_type == 'buy' else 'WTS'
    lines = [f'{label} inquiry']
    if rule.include_inquiry_id:
        lines.extend(['', f'Inquiry ID: #{inquiry.pk}'])
    if rule.include_original_message:
        text = (source.message_text or '').strip()
        if not text:
            return ''
        lines.extend(['', 'Original message:', text])

    products = [row for row in inquiry.products if isinstance(row, dict) and product_name(row)]
    if rule.include_summary and (inquiry.summary or '').strip():
        lines.extend(['', 'Summary:', inquiry.summary.strip()])

    suggestions = _stock_suggestions(inquiry, products) if rule.include_stock_suggestions else []
    if suggestions:
        lines.extend(['', 'In-stock exact matches:', *suggestions])
    if rule.include_sender_link:
        lines.extend(['', f'Direct chat: {sender_link(source)}'])
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
