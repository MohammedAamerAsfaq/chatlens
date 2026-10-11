from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def property_media_path(instance, filename):
    return f'real-estate/properties/{instance.property_id}/{filename}'


class PropertyMedia(models.Model):
    TYPE_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        'image', 'video', 'floor_plan', 'brochure', 'document',
    )]
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_media')
    property = models.ForeignKey('real_estate.Property', on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='image')
    file = models.FileField(upload_to=property_media_path, blank=True)
    external_url = models.URLField(max_length=1000, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'real_estate_property_media'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['property'], condition=Q(is_primary=True), name='re_property_single_primary_media'),
        ]

    def clean(self):
        super().clean()
        from apps.real_estate.services.media_validation import validate_property_media_file

        errors = {}
        if self.property_id and self.property.company_id != self.company_id:
            errors['property'] = 'The property must belong to this company.'
        if bool(self.file) == bool(self.external_url):
            errors['file'] = 'Provide exactly one uploaded file or external URL.'
        elif self.file:
            try:
                validate_property_media_file(self.file)
            except ValidationError as exc:
                errors['file'] = exc.messages
        if errors:
            raise ValidationError(errors)
