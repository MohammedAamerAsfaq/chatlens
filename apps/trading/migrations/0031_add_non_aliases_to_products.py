from django.db import migrations


ALIASES = ('non active', 'non')


def add_non_aliases(apps, schema_editor):
    Product = apps.get_model('trading', 'Product')
    ProductAlias = apps.get_model('trading', 'ProductAlias')

    rows = []
    existing = set(
        ProductAlias.objects
        .filter(alias__in=ALIASES)
        .values_list('product_id', 'alias')
    )
    for product_id in Product.objects.values_list('id', flat=True):
        for alias in ALIASES:
            if (product_id, alias) not in existing:
                rows.append(ProductAlias(product_id=product_id, alias=alias))

    ProductAlias.objects.bulk_create(rows, ignore_conflicts=True)


def remove_non_aliases(apps, schema_editor):
    ProductAlias = apps.get_model('trading', 'ProductAlias')
    ProductAlias.objects.filter(alias__in=ALIASES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0030_aiparsev2log'),
    ]

    operations = [
        migrations.RunPython(add_non_aliases, remove_non_aliases),
    ]
