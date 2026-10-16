from rest_framework import serializers

from .models import AdministrativeArea, City, Country, IntegrationSyncRun


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ('id', 'iso2', 'iso3', 'name', 'latitude', 'longitude', 'is_active', 'source_updated_at')


class AdministrativeAreaSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.iso2', read_only=True)

    class Meta:
        model = AdministrativeArea
        fields = (
            'id', 'country_code', 'level', 'code', 'name', 'latitude',
            'longitude', 'is_active', 'source_updated_at',
        )


class CitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.iso2', read_only=True)
    administrative_area_name = serializers.CharField(source='administrative_area.name', read_only=True)

    class Meta:
        model = City
        fields = (
            'id', 'country_code', 'administrative_area_name', 'name', 'feature_code',
            'latitude', 'longitude', 'population', 'timezone', 'is_active', 'source_updated_at',
        )


class IntegrationSyncRunSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source='connection.provider', read_only=True)

    class Meta:
        model = IntegrationSyncRun
        fields = (
            'id', 'provider', 'resource', 'country_code', 'status',
            'background_task_id', 'counters', 'error', 'started_at',
            'finished_at', 'created_at',
        )
