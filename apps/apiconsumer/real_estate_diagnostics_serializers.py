from rest_framework import serializers

from apps.real_estate.models import RealEstateAgentCallLog, RealEstateParseLog


class RealEstateParseLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealEstateParseLog
        fields = [
            'id', 'message_id', 'account_id', 'chat_id', 'opportunity_id',
            'status', 'skip_reason', 'gate_mode', 'gate_decision', 'gate_request',
            'gate_response', 'gate_duration_ms', 'extraction_request', 'extraction_response',
            'extraction_result', 'extraction_duration_ms', 'total_duration_ms', 'error',
            'created_at', 'updated_at',
        ]


class RealEstateAgentCallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealEstateAgentCallLog
        fields = [
            'id', 'purpose', 'provider', 'model', 'messages', 'response',
            'input_tokens', 'output_tokens', 'duration_ms', 'success', 'error',
            'wa_message_id', 'created_at',
        ]
