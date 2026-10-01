from django.conf import settings
from django.db import models


class ContactMergeCandidate(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_MERGED = 'merged'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending review'),
        (STATUS_MERGED, 'Merged'),
        (STATUS_REJECTED, 'Not a duplicate'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='contact_merge_candidates',
    )
    left_contact = models.ForeignKey(
        'tenancy.CompanyContact', on_delete=models.CASCADE, related_name='merge_candidates_left',
    )
    right_contact = models.ForeignKey(
        'tenancy.CompanyContact', on_delete=models.CASCADE, related_name='merge_candidates_right',
    )
    match_reasons = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='contact_merge_candidates_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_contact_merge_candidate'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'left_contact', 'right_contact'],
                name='unique_contact_merge_candidate_pair',
            ),
            models.CheckConstraint(
                condition=~models.Q(left_contact=models.F('right_contact')),
                name='contact_merge_candidate_distinct_contacts',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.left_contact_id and self.right_contact_id:
            if self.left_contact_id > self.right_contact_id:
                self.left_contact_id, self.right_contact_id = (
                    self.right_contact_id, self.left_contact_id,
                )
            contact_companies = {self.left_contact.company_id, self.right_contact.company_id}
            if contact_companies != {self.company_id}:
                raise ValueError('Merge candidates must contain contacts from one company.')
        super().save(*args, **kwargs)
