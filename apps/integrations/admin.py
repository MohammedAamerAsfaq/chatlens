from django.contrib import admin

from .models import (
    AdministrativeArea, City, Country, GeographyExternalReference, IntegrationConnection,
    IntegrationSyncRun, IntegrationUsagePeriod, Locality,
)


@admin.register(IntegrationConnection)
class IntegrationConnectionAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'provider', 'scope', 'company', 'status', 'is_enabled')
    list_filter = ('provider', 'scope', 'status', 'is_enabled')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'iso2', 'iso3', 'geoname_id', 'is_active')
    search_fields = ('name', 'iso2', 'iso3')


@admin.register(AdministrativeArea)
class AdministrativeAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'level', 'code', 'geoname_id', 'is_active')
    list_filter = ('country', 'level', 'is_active')
    search_fields = ('name', 'code')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'administrative_area', 'population', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('name',)


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'country', 'administrative_area', 'city', 'feature_code',
        'mapping_status', 'is_active',
    )
    list_filter = ('country', 'administrative_area', 'mapping_status', 'is_active')
    search_fields = ('name',)


@admin.register(IntegrationSyncRun)
class IntegrationSyncRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'connection', 'resource', 'country_code', 'status', 'created_at')
    list_filter = ('status', 'resource', 'country_code')


@admin.register(GeographyExternalReference)
class GeographyExternalReferenceAdmin(admin.ModelAdmin):
    list_display = ('locality', 'city', 'provider', 'external_id', 'status', 'verified_at')
    list_filter = ('provider', 'status')
    search_fields = ('locality__name', 'city__name', 'external_id')


@admin.register(IntegrationUsagePeriod)
class IntegrationUsagePeriodAdmin(admin.ModelAdmin):
    list_display = ('connection', 'period_start', 'request_count', 'updated_at')
