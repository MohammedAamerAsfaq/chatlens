from django.db import models


class ApiKeyUsageLog(models.Model):
    api_key = models.ForeignKey(
        'apiconsumer.ApiKey', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='usage_logs',
    )
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='api_usage_logs')
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'apiconsumer_api_key_usage_log'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'created_at'])]
