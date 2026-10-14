from rest_framework import serializers

from apps.real_estate.models import RealEstateMockSourceRecord


class RealEstateMockSourceRecordSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = RealEstateMockSourceRecord
        fields = (
            'id', 'company_id', 'import_run_id', 'source_file_name',
            'source_file_checksum', 'source_sheet_name', 'source_sheet_index',
            'source_row_number', 'row_kind', 'raw_values', 'display_values',
            'row_checksum', 'processing_status', 'processing_notes', 'imported_at',
        )
        read_only_fields = fields
