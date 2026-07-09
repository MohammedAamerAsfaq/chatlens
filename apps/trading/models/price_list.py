from django.db import models


class FormattedPriceList(models.Model):
    """
    Singleton (always pk=1): the AI-formatted price list text, regenerated on demand
    from the current in-stock priced catalog via the 'price_list_format' prompt.
    Used verbatim as the prefill text for the "Price List" WhatsApp button, instead of
    building that text ad hoc on every click.
    """
    body         = models.TextField(blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_formatted_price_list'

    def __str__(self):
        return f'Formatted price list (generated {self.generated_at})'

    @classmethod
    def get_current(cls):
        return cls.objects.filter(pk=1).first()
