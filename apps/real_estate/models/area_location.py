from django.db import models


class AreaLocation(models.Model):
    """Where an area (community or district, with its city) sits on the map.

    Areas come from the Real Estate Location AI step. Each distinct area is placed once per
    company and remembered, first from the geography directory (free) and otherwise through
    Google Maps (one paid request).
    """

    SOURCE_DIRECTORY = 'directory'
    SOURCE_GOOGLE = 'google'
    SOURCE_CHOICES = [(SOURCE_DIRECTORY, 'Geography directory'), (SOURCE_GOOGLE, 'Google Maps')]

    STATUS_PLACED = 'placed'
    STATUS_PENDING = 'pending'
    STATUS_NOT_FOUND = 'not_found'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_PLACED, 'On the map'),
        (STATUS_PENDING, 'Waiting for a Google Maps lookup'),
        (STATUS_NOT_FOUND, 'Not found'),
        (STATUS_ERROR, 'Lookup failed'),
    ]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_area_locations')
    normalized_name = models.CharField(max_length=200)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    matched_label = models.CharField(max_length=300, blank=True, help_text='What the name was matched to.')
    error = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Set when this name was merged into another area on the Area Map: later results with
    # this name go to that area.
    merged_into = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='merged_names')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_area_location'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['company', 'normalized_name'], name='re_area_location_company_name_uniq'),
        ]
        indexes = [models.Index(fields=['company', 'status'])]

    def __str__(self):
        return f'{self.name} ({self.status})'
