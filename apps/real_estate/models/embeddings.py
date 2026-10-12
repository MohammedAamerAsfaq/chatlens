from django.core.exceptions import ValidationError
from django.db import models
from pgvector.django import VectorField


class EmbeddingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    EMBEDDED = 'embedded', 'Embedded'
    ERROR = 'error', 'Error'
    SKIPPED = 'skipped', 'Skipped'


class RealEstateEmbeddingBase(models.Model):
    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.PENDING,
        db_index=True,
    )
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def validate_target_company(self, target):
        if target and target.company_id != self.company_id:
            raise ValidationError({'company': 'The embedding and target must belong to the same company.'})


class PropertyEmbedding(RealEstateEmbeddingBase):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_property_embeddings',
    )
    property = models.OneToOneField(
        'real_estate.Property', on_delete=models.CASCADE, related_name='embedding_record',
    )

    class Meta:
        db_table = 'real_estate_property_embedding'
        indexes = [models.Index(fields=['company', 'status'])]

    def clean(self):
        super().clean()
        self.validate_target_company(self.property if self.property_id else None)


class ListingEmbedding(RealEstateEmbeddingBase):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_listing_embeddings',
    )
    listing = models.OneToOneField(
        'real_estate.Listing', on_delete=models.CASCADE, related_name='embedding_record',
    )

    class Meta:
        db_table = 'real_estate_listing_embedding'
        indexes = [models.Index(fields=['company', 'status'])]

    def clean(self):
        super().clean()
        self.validate_target_company(self.listing if self.listing_id else None)


class RequirementEmbedding(RealEstateEmbeddingBase):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_requirement_embeddings',
    )
    requirement = models.OneToOneField(
        'real_estate.PropertyRequirement', on_delete=models.CASCADE, related_name='embedding_record',
    )

    class Meta:
        db_table = 'real_estate_requirement_embedding'
        indexes = [models.Index(fields=['company', 'status'])]

    def clean(self):
        super().clean()
        self.validate_target_company(self.requirement if self.requirement_id else None)


class CandidateEmbedding(RealEstateEmbeddingBase):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_candidate_embeddings',
    )
    candidate = models.OneToOneField(
        'real_estate.PropertyCandidate', on_delete=models.CASCADE, related_name='embedding_record',
    )

    class Meta:
        db_table = 'real_estate_candidate_embedding'
        indexes = [models.Index(fields=['company', 'status'])]

    def clean(self):
        super().clean()
        self.validate_target_company(self.candidate if self.candidate_id else None)
