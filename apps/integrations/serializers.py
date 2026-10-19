from rest_framework import serializers

from .models import AdministrativeArea, City, Country, IntegrationSyncRun, Locality


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
    administrative_area_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = City
        fields = (
            'id', 'country_code', 'administrative_area_id', 'administrative_area_name', 'name', 'feature_code',
            'latitude', 'longitude', 'population', 'timezone', 'is_active', 'source_updated_at',
        )


class LocalitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.iso2', read_only=True)
    administrative_area_name = serializers.CharField(source='administrative_area.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    administrative_area_id = serializers.IntegerField(read_only=True)
    google_reference = serializers.SerializerMethodField()

    def get_google_reference(self, obj):
        reference = next((item for item in obj.external_references.all() if item.provider == 'google_maps'), None)
        if not reference:
            return None
        return {
            'place_id': reference.external_id,
            'status': reference.status,
            'verified_at': reference.verified_at,
        }

    class Meta:
        model = Locality
        fields = (
            'id', 'country_code', 'administrative_area_id', 'administrative_area_name',
            'city_name', 'name', 'google_reference',
            'feature_code', 'latitude', 'longitude', 'population', 'timezone',
            'mapping_status', 'is_active', 'source_updated_at',
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
