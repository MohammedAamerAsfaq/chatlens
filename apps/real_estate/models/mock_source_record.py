from django.db import models


class RealEstateMockSourceRecord(models.Model):
    ROW_KIND_CHOICES = [
        ('header', 'Header'),
        ('data', 'Data'),
        ('summary', 'Summary'),
        ('unknown', 'Unknown'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_mock_source_records',
    )
    import_run_id = models.UUIDField(db_index=True)
    source_file_name = models.CharField(max_length=500)
    source_file_checksum = models.CharField(max_length=64, db_index=True)
    source_sheet_name = models.CharField(max_length=255)
    source_sheet_index = models.PositiveIntegerField()
    source_row_number = models.PositiveIntegerField()
    row_kind = models.CharField(max_length=16, choices=ROW_KIND_CHOICES, default='data')
    raw_values = models.JSONField(default=list)
    display_values = models.JSONField(default=list)
    row_checksum = models.CharField(max_length=64)
    processing_status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='pending', db_index=True,
    )
    processing_notes = models.TextField(blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'real_estate_mock_source_record'
        ordering = ['source_file_name', 'source_sheet_index', 'source_row_number']
        constraints = [models.UniqueConstraint(
            fields=[
                'company', 'source_file_name', 'source_file_checksum',
                'source_sheet_index', 'source_row_number',
            ],
            name='re_mock_source_identity_uniq',
        )]
        indexes = [
            models.Index(fields=['company', 'processing_status'], name='re_mock_company_status_idx'),
            models.Index(fields=['company', 'source_file_name'], name='re_mock_company_file_idx'),
        ]

    def __str__(self):
        return f'{self.source_file_name}:{self.source_sheet_name}:{self.source_row_number}'
