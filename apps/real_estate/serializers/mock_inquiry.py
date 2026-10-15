from rest_framework import serializers

from apps.real_estate.models import RealEstateMockInquiry, RealEstateMockInquiryRun


class RealEstateMockInquiryRunSerializer(serializers.ModelSerializer):
    task_status = serializers.CharField(source='task.status', read_only=True, default='')
    mock_account_name = serializers.CharField(source='mock_account.display_name', read_only=True, default='')

    class Meta:
        model = RealEstateMockInquiryRun
        fields = (
            'id', 'company_id', 'source_file_name', 'activity_type',
            'requested_count', 'generated_count', 'failed_count', 'status',
            'task_id', 'task_status', 'mock_account_id', 'mock_account_name',
            'error', 'started_at', 'finished_at', 'created_at',
        )
        read_only_fields = fields


class RealEstateMockInquirySerializer(serializers.ModelSerializer):
    source_sheet_name = serializers.CharField(source='source_record.source_sheet_name', read_only=True, default='')
    source_row_number = serializers.IntegerField(source='source_record.source_row_number', read_only=True, default=None)
    live_task_status = serializers.CharField(source='live_task.status', read_only=True, default='')
    parse_status = serializers.SerializerMethodField()
    embedding_status = serializers.SerializerMethodField()
    classified_activity = serializers.SerializerMethodField()

    class Meta:
        model = RealEstateMockInquiry
        fields = (
            'id', 'run_id', 'source_record_id', 'source_sheet_name',
            'source_row_number', 'activity_type', 'contact_name', 'contact_number',
            'generated_message', 'provider_message_id', 'live_task_id',
            'live_task_status', 'message_id', 'status', 'parse_status',
            'embedding_status', 'classified_activity', 'error', 'created_at',
        )
        read_only_fields = fields

    def get_parse_status(self, obj):
        log = getattr(obj.message, 'real_estate_parse_log', None) if obj.message_id else None
        return getattr(log, 'status', '')

    def get_embedding_status(self, obj):
        if not obj.message_id:
            return 'pending'
        return 'complete' if hasattr(obj.message, 'embedding') else 'pending'

    def get_classified_activity(self, obj):
        if not obj.message_id:
            return ''
        opportunity = getattr(obj.message, 'real_estate_opportunity', None)
        return getattr(opportunity, 'activity_type', '')
