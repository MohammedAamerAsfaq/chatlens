from django.db import models


class Intent(models.TextChoices):
    PRICE_INQUIRY = 'price_inquiry', 'Price Inquiry'
    STOCK_INQUIRY = 'stock_inquiry', 'Stock Inquiry'
    ORDER_REQUEST = 'order_request', 'Order Request'
    INVOICE_REQUEST = 'invoice_request', 'Invoice Request'
    PAYMENT_FOLLOWUP = 'payment_followup', 'Payment Follow-up'
    DELIVERY_FOLLOWUP = 'delivery_followup', 'Delivery Follow-up'
    WARRANTY_COMPLAINT = 'warranty_complaint', 'Warranty Complaint'
    GENERAL_COMPLAINT = 'general_complaint', 'General Complaint'
    GREETING = 'greeting', 'Greeting'
    UNKNOWN = 'unknown', 'Unknown'


class Sentiment(models.TextChoices):
    POSITIVE = 'positive', 'Positive'
    NEUTRAL = 'neutral', 'Neutral'
    NEGATIVE = 'negative', 'Negative'


class MessageAnalysis(models.Model):
    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='analysis',
    )
    language = models.CharField(max_length=20, blank=True)
    sentiment = models.CharField(
        max_length=50,
        choices=Sentiment.choices,
        blank=True,
    )
    intent = models.CharField(
        max_length=100,
        choices=Intent.choices,
        default=Intent.UNKNOWN,
    )
    urgency_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lead_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    product_mentions = models.JSONField(null=True, blank=True)
    extracted_entities = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_analysis'

    def __str__(self):
        return f"Analysis for message {self.message_id} | {self.intent}"
