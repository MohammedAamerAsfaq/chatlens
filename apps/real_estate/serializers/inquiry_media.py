from rest_framework import serializers

from apps.real_estate.models import InquiryMedium
from apps.real_estate.serializers.base import CleanModelSerializer
from apps.real_estate.services.inquiry_media import unique_medium_code


class InquiryMediumSerializer(CleanModelSerializer):
    class Meta:
        model = InquiryMedium
        exclude = ('company',)
        read_only_fields = ('code', 'created_at', 'updated_at')

    def create(self, validated_data):
        company = self.context['view'].active_company()
        validated_data['code'] = unique_medium_code(company, validated_data['name'])
        return super().create(validated_data)
