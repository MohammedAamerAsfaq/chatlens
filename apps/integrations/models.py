import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class IntegrationConnection(models.Model):
    SCOPE_PLATFORM = 'platform'
    SCOPE_COMPANY = 'company'
    PROVIDER_GEONAMES = 'geonames'
    PROVIDER_GOOGLE_MAPS = 'google_maps'
    PROVIDER_GOOGLE_CONTACTS = 'google_contacts'
    STATUS_NOT_CONFIGURED = 'not_configured'
    STATUS_READY = 'ready'
    STATUS_ERROR = 'error'

    scope = models.CharField(max_length=20, choices=[
        (SCOPE_PLATFORM, 'Platform'), (SCOPE_COMPANY, 'Company'),
    ])
    company = models.ForeignKey(
        'tenancy.Company', null=True, blank=True, on_delete=models.CASCADE,
        related_name='integration_connections',
    )
    provider = models.CharField(max_length=40, choices=[
        (PROVIDER_GEONAMES, 'GeoNames'),
        (PROVIDER_GOOGLE_MAPS, 'Google Maps'),
        (PROVIDER_GOOGLE_CONTACTS, 'Google Contacts'),
    ])
    display_name = models.CharField(max_length=120)
    configuration = models.JSONField(default=dict, blank=True)
    secret_reference = models.CharField(
        max_length=255, blank=True,
        help_text='Reference to an external secret; secret values are not stored here.',
    )
    is_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=30, default=STATUS_NOT_CONFIGURED, choices=[
        (STATUS_NOT_CONFIGURED, 'Not configured'),
        (STATUS_READY, 'Ready'), (STATUS_ERROR, 'Error'),
    ])
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_successful_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='integration_connections_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_connection'
        ordering = ['provider', 'display_name']
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope='platform', company__isnull=True)
                    | Q(scope='company', company__isnull=False)
                ), name='integration_connection_valid_scope',
            ),
            models.UniqueConstraint(
                fields=['provider'], condition=Q(scope='platform'),
                name='unique_platform_integration_provider',
            ),
            models.UniqueConstraint(
                fields=['company', 'provider'], condition=Q(scope='company'),
                name='unique_company_integration_provider',
            ),
        ]

    def __str__(self):
        return self.display_name


class Country(models.Model):
    iso2 = models.CharField(max_length=2, unique=True)
    iso3 = models.CharField(max_length=3, blank=True)
    name = models.CharField(max_length=150)
    normalized_name = models.CharField(max_length=150, db_index=True)
    geoname_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    alternate_names = models.JSONField(default=list, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geo_country'
        ordering = ['name']

    def __str__(self):
        return self.name


class AdministrativeArea(models.Model):
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='administrative_areas')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='children',
    )
    level = models.PositiveSmallIntegerField(default=1)
    code = models.CharField(max_length=40, blank=True, db_index=True)
    name = models.CharField(max_length=150)
    normalized_name = models.CharField(max_length=150, db_index=True)
    geoname_id = models.PositiveBigIntegerField(unique=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    alternate_names = models.JSONField(default=list, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geo_administrative_area'
        ordering = ['country__name', 'level', 'name']
        indexes = [models.Index(fields=['country', 'level', 'normalized_name'])]

    def __str__(self):
        return f'{self.name}, {self.country.iso2}'


class City(models.Model):
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='cities')
    administrative_area = models.ForeignKey(
        AdministrativeArea, null=True, blank=True, on_delete=models.PROTECT,
        related_name='cities',
    )
    name = models.CharField(max_length=150)
    normalized_name = models.CharField(max_length=150, db_index=True)
    geoname_id = models.PositiveBigIntegerField(unique=True)
    feature_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    population = models.PositiveBigIntegerField(default=0)
    timezone = models.CharField(max_length=80, blank=True)
    alternate_names = models.JSONField(default=list, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geo_city'
        ordering = ['country__name', 'name']
        indexes = [models.Index(fields=['country', 'administrative_area', 'normalized_name'])]

    def __str__(self):
        return f'{self.name}, {self.country.iso2}'


class Locality(models.Model):
    MAPPING_MAPPED = 'mapped'
    MAPPING_UNMAPPED = 'unmapped'
    MAPPING_REVIEW = 'review'
    MAPPING_CHOICES = [
        (MAPPING_MAPPED, 'Mapped'),
        (MAPPING_UNMAPPED, 'Unmapped'),
        (MAPPING_REVIEW, 'Needs review'),
    ]

    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='localities')
    administrative_area = models.ForeignKey(
        AdministrativeArea, null=True, blank=True, on_delete=models.PROTECT,
        related_name='localities',
    )
    city = models.ForeignKey(
        City, null=True, blank=True, on_delete=models.PROTECT, related_name='localities',
    )
    name = models.CharField(max_length=150)
    normalized_name = models.CharField(max_length=150, db_index=True)
    geoname_id = models.PositiveBigIntegerField(unique=True)
    feature_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    population = models.PositiveBigIntegerField(default=0)
    timezone = models.CharField(max_length=80, blank=True)
    alternate_names = models.JSONField(default=list, blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    mapping_status = models.CharField(
        max_length=20, choices=MAPPING_CHOICES, default=MAPPING_UNMAPPED, db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geo_locality'
        ordering = ['country__name', 'name']
        indexes = [
            models.Index(
                fields=['country', 'administrative_area', 'city', 'normalized_name'],
                name='geo_locality_hierarchy_idx',
            ),
        ]

    def __str__(self):
        return f'{self.name}, {self.country.iso2}'


class IntegrationSyncRun(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.PROTECT, related_name='sync_runs',
    )
    company = models.ForeignKey(
        'tenancy.Company', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='integration_sync_runs',
    )
    resource = models.CharField(max_length=80)
    country_code = models.CharField(max_length=2, blank=True)
    status = models.CharField(max_length=20, default=STATUS_PENDING, choices=[
        (STATUS_PENDING, 'Pending'), (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'), (STATUS_FAILED, 'Failed'),
    ])
    background_task_id = models.PositiveBigIntegerField(null=True, blank=True)
    counters = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='integration_sync_runs_requested',
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_sync_run'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['connection', 'resource', 'country_code'],
                condition=Q(status__in=['pending', 'running']),
                name='unique_active_integration_sync',
            ),
        ]
