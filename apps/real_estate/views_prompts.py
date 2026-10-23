from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_providers.models import AIProviderConfig, KiwiRouter
from apps.real_estate.models import (
    RealEstateAgentCallLog, RealEstateOpportunity, RealEstatePromptConfig, RealEstateSettings,
)
from apps.real_estate.services.prompts import DEFAULT_PROMPTS
from apps.tenancy.models import Company
from apps.tenancy.permissions import CompanyAdminPermission
from apps.tenancy.services.access import default_company_for_user


class RealEstatePromptViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, CompanyAdminPermission]
    # Reading the card display config must work for every board viewer so the board
    # actually renders the admin's chosen layout for everyone, not just admins —
    # only saving changes is admin-gated.
    _read_only_for_any_member = {('card_field_config', 'GET'), ('card_action_config', 'GET')}

    def get_permissions(self):
        if (self.action, self.request.method) in self._read_only_for_any_member:
            return [IsAuthenticated()]
        return super().get_permissions()

    def company(self):
        company = default_company_for_user(self.request.user)
        if not company or (
            company.industry_type != Company.INDUSTRY_REAL_ESTATE
            and company.company_type != Company.TYPE_CONTROL
        ):
            return None
        return company

    @staticmethod
    def serialize_prompt(obj, key, label, default_body):
        return {
            'key': key,
            'label': label,
            'body': obj.body if obj else default_body,
            'is_default': obj is None,
            'updated_at': obj.updated_at.isoformat() if obj else None,
            'agent_config': obj.agent_config_id if obj else None,
            'kiwi_router': obj.kiwi_router_id if obj else None,
            'uses_kiwi_router': bool(obj and obj.kiwi_router_id),
        }

    def list(self, request):
        company = self.company()
        if not company:
            return Response({'detail': 'A Real Estate company is required.'}, status=403)
        saved = {
            item.key: item for item in RealEstatePromptConfig.objects.filter(company=company)
        }
        return Response([
            self.serialize_prompt(saved.get(key), key, label, body)
            for key, (body, label) in DEFAULT_PROMPTS.items()
        ])

    def partial_update(self, request, pk=None):
        company = self.company()
        if not company:
            return Response({'detail': 'A Real Estate company is required.'}, status=403)
        if pk not in DEFAULT_PROMPTS:
            return Response({'error': f'Unknown prompt key: {pk}'}, status=400)
        default_body, label = DEFAULT_PROMPTS[pk]
        existing = RealEstatePromptConfig.objects.filter(company=company, key=pk).first()
        body = str(request.data.get('body', existing.body if existing else default_body)).strip()
        if not body:
            return Response({'error': 'body is required'}, status=400)
        agent, router, error = self.resolve_target(company, existing, request.data)
        if error:
            return Response({'error': error}, status=400)
        obj, _created = RealEstatePromptConfig.objects.update_or_create(
            company=company,
            key=pk,
            defaults={
                'label': label,
                'body': body,
                'agent_config': agent,
                'kiwi_router': router,
            },
        )
        return Response(self.serialize_prompt(obj, pk, label, default_body))

    @staticmethod
    def resolve_target(company, existing, data):
        agent = existing.agent_config if existing else None
        router = existing.kiwi_router if existing else None
        if 'kiwi_router' in data:
            router = None
            if data.get('kiwi_router') not in ('', None):
                router = KiwiRouter.objects.filter(
                    pk=data['kiwi_router'], company=company, capability='agent', is_active=True,
                ).first()
                if not router:
                    return None, None, 'Selected KiwiRouter is invalid or inactive.'
                agent = None
        if 'agent_config' in data:
            agent = None
            if data.get('agent_config') not in ('', None):
                agent = AIProviderConfig.objects.filter(
                    pk=data['agent_config'], company=company, capability='agent',
                ).first()
                if not agent:
                    return None, None, 'Selected AI agent is invalid.'
                router = None
        return agent, router, ''

    def destroy(self, request, pk=None):
        company = self.company()
        if not company:
            return Response({'detail': 'A Real Estate company is required.'}, status=403)
        RealEstatePromptConfig.objects.filter(company=company, key=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='agent-options')
    def agent_options(self, request):
        company = self.company()
        rows = AIProviderConfig.objects.filter(company=company, capability='agent').order_by(
            '-is_active', 'display_name',
        ) if company else []
        return Response([{
            'id': row.pk, 'display_name': row.display_name, 'provider': row.provider,
            'model': row.model, 'is_active': row.is_active,
        } for row in rows])

    @action(detail=False, methods=['get'], url_path='kiwi-router-options')
    def router_options(self, request):
        company = self.company()
        rows = KiwiRouter.objects.filter(
            company=company, capability='agent', is_active=True,
        ).order_by('name') if company else []
        return Response([{
            'id': row.pk, 'name': row.name, 'member_count': row.members.count(),
        } for row in rows])

    @action(detail=False, methods=['get'], url_path='agent-logs')
    def agent_logs(self, request):
        company = self.company()
        rows = RealEstateAgentCallLog.objects.filter(company=company) if company else []
        if purpose := request.query_params.get('purpose'):
            rows = rows.filter(purpose=purpose)
        if success := request.query_params.get('success'):
            rows = rows.filter(success=success == 'true')
        return Response([{
            'id': row.pk, 'purpose': row.purpose, 'provider': row.provider, 'model': row.model,
            'messages': row.messages, 'response': row.response, 'input_tokens': row.input_tokens,
            'output_tokens': row.output_tokens, 'duration_ms': row.duration_ms,
            'success': row.success, 'error': row.error, 'wa_message_id': row.wa_message_id,
            'created_at': row.created_at.isoformat(), 'input_cost': None, 'output_cost': None,
        } for row in rows[:200]])

    @action(detail=False, methods=['get', 'put'], url_path='card-field-config')
    def card_field_config(self, request):
        """Ordered list of field ids (see frontend cardFields.js registry) to show on
        Opportunity Board cards. Opaque ids — the frontend registry is the single
        source of truth for what each one means and renders as; this just persists
        the admin's chosen subset/order per company."""
        company = self.company()
        if not company:
            return Response({'detail': 'A Real Estate company is required.'}, status=403)
        settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
        if request.method == 'GET':
            return Response({'fields': settings_row.card_field_config})
        fields = request.data.get('fields')
        if not isinstance(fields, list) or not all(isinstance(value, str) for value in fields):
            return Response({'error': 'fields must be a list of strings'}, status=400)
        settings_row.card_field_config = fields
        settings_row.save(update_fields=['card_field_config', 'updated_at'])
        return Response({'fields': settings_row.card_field_config})

    @action(detail=False, methods=['get', 'put'], url_path='card-action-config')
    def card_action_config(self, request):
        """Which RealEstateOpportunity.status values get a quick-set button in the card
        footer, in what order, and how many render inline before the rest collapse into
        a 'More' dropdown. No new status/action concept — these are the opportunity's
        existing status values, just exposed as one-click buttons."""
        company = self.company()
        if not company:
            return Response({'detail': 'A Real Estate company is required.'}, status=403)
        settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
        if request.method == 'GET':
            return Response(settings_row.card_action_config or {'statuses': [], 'max_inline': 2})
        statuses = request.data.get('statuses')
        max_inline = request.data.get('max_inline', 2)
        if not isinstance(statuses, list) or not all(isinstance(value, str) for value in statuses):
            return Response({'error': 'statuses must be a list of strings'}, status=400)
        valid_statuses = {value for value, _ in RealEstateOpportunity.STATUS_CHOICES}
        if not set(statuses) <= valid_statuses:
            return Response({'error': 'statuses contains an unknown status value'}, status=400)
        if not isinstance(max_inline, int) or max_inline < 0:
            return Response({'error': 'max_inline must be a non-negative integer'}, status=400)
        settings_row.card_action_config = {'statuses': statuses, 'max_inline': max_inline}
        settings_row.save(update_fields=['card_action_config', 'updated_at'])
        return Response(settings_row.card_action_config)
