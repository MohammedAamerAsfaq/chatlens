from django.db import models


class InquiryMedium(models.Model):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_inquiry_media',
    )
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=80)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_inquiry_medium'
        ordering = ['sort_order', 'name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='real_estate_company_medium_code_uniq',
            ),
        ]

    def __str__(self):
        return self.name
