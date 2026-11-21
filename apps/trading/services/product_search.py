from django.db.models import Q, Value
from django.db.models.functions import Concat


def search_products(qs, search):
    """Products matching a typed search. Names do not repeat the brand, so "samsung a15" is also
    matched against brand + name together, besides the name, brand, SKU and aliases alone."""
    search = (search or '').strip()
    if not search:
        return qs
    return qs.annotate(_brand_and_name=Concat('brand', Value(' '), 'name')).filter(
        Q(_brand_and_name__icontains=search)
        | Q(name__icontains=search)
        | Q(brand__icontains=search)
        | Q(sku__icontains=search)
        | Q(alias_set__alias__icontains=search)
    ).distinct()
