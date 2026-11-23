from rest_framework import serializers

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import MarketPriceReference, PropertyType


class MarketPriceReferenceSerializer(serializers.ModelSerializer):
    property_type = serializers.PrimaryKeyRelatedField(
        queryset=PropertyType.objects.all(), allow_null=True, required=False,
    )
    property_type_name = serializers.CharField(source='property_type.name', read_only=True, default='')

    class Meta:
        model = MarketPriceReference
        fields = (
            'id', 'location', 'property_type', 'property_type_name', 'bedrooms',
            'sale_price_min', 'sale_price_max', 'currency', 'notes', 'updated_at',
        )
        read_only_fields = ('updated_at',)

    def validate_location(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter the area, community or building.')
        return value

    def validate_property_type(self, value):
        company = self.context['view'].active_company()
        if value is not None and value.company_id != company.pk:
            raise serializers.ValidationError('Select a property type of this company.')
        return value

    def validate_currency(self, value):
        value = (value or '').strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError('Use a 3-letter currency code, e.g. AED.')
        return value

    def validate_bedrooms(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Bedrooms cannot be negative.')
        return value

    def validate(self, data):
        low = data.get('sale_price_min', getattr(self.instance, 'sale_price_min', None))
        high = data.get('sale_price_max', getattr(self.instance, 'sale_price_max', None))
        if low is not None and low <= 0:
            raise serializers.ValidationError({'sale_price_min': 'Enter a sale price above 0.'})
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({'sale_price_max': 'The highest price must be at least the lowest.'})
        return data


class MarketPriceReferenceViewSet(CompanyOwnedViewSet):
    """The company's typical sale prices, used by the extraction price check when the
    company chooses its own price table (RealEstateSettings.price_check_mode)."""
    queryset = MarketPriceReference.objects.select_related('property_type')
    serializer_class = MarketPriceReferenceSerializer
    read_permission = 'settings.company.manage'
    write_permission = 'settings.company.manage'
    pagination_class = None
