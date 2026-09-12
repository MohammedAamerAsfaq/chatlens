import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import AIProviderConfig, DefaultAgentTarget, KiwiRouter, KiwiRoutingDecision
from .serializers import AIProviderConfigSerializer, KiwiRouterSerializer, KiwiRoutingDecisionSerializer, PROVIDER_MODELS
from .manager import build_provider

logger = logging.getLogger(__name__)


class AIProviderConfigViewSet(viewsets.ModelViewSet):
    queryset = AIProviderConfig.objects.all()
    serializer_class = AIProviderConfigSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        config = self.get_object()
        # Deactivate any currently active provider for this capability
        AIProviderConfig.objects.filter(
            capability=config.capability, is_active=True
        ).exclude(pk=config.pk).update(is_active=False)
        config.is_active = True
        config.save(update_fields=['is_active'])
        return Response(self.get_serializer(config).data)

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        config = self.get_object()
        config.is_active = False
        config.save(update_fields=['is_active'])
        return Response(self.get_serializer(config).data)

    @action(detail=False, methods=['get', 'patch'], url_path='agent-target')
    def agent_target(self, request):
        """Read or choose the default target for general AI agent work."""
        target, _ = DefaultAgentTarget.objects.get_or_create(pk=1)
        if request.method == 'PATCH':
            router_id = request.data.get('kiwi_router_id')
            if router_id in ('', None):
                target.kiwi_router = None
            else:
                router = KiwiRouter.objects.filter(
                    pk=router_id,
                    capability=AIProviderConfig.CAPABILITY_AGENT,
                    is_active=True,
                ).first()
                if not router:
                    return Response(
                        {'error': 'Select an active General AI Agent KiwiRouter.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                target.kiwi_router = router
            target.save()
        target = DefaultAgentTarget.objects.select_related('kiwi_router').get(pk=target.pk)
        return Response({
            'mode': 'kiwi_router' if target.kiwi_router else 'direct',
            'kiwi_router_id': target.kiwi_router_id,
            'kiwi_router_name': target.kiwi_router.name if target.kiwi_router else '',
        })

    @action(detail=True, methods=['post'], url_path='test')
    def test_connection(self, request, pk=None):
        config = self.get_object()
        try:
            result = build_provider(config).test_connection()
        except Exception as e:
            logger.exception('Provider test failed for config %s', pk)
            result = {'ok': False, 'error': str(e)}
        return Response(result)

    @action(detail=True, methods=['post'], url_path='fetch-metadata')
    def fetch_metadata(self, request, pk=None):
        """Return provider-published account metadata when an adapter supports it."""
        config = self.get_object()
        provider = build_provider(config)
        fetch = getattr(provider, 'fetch_metadata', None)
        if callable(fetch):
            try:
                result = fetch() or {}
            except Exception as exc:
                logger.warning('Metadata fetch failed for provider config %s: %s', pk, exc)
                return Response({
                    'metadata': {},
                    'available': False,
                    'detail': f'Provider metadata request failed: {exc}',
                }, status=status.HTTP_502_BAD_GATEWAY)
            return Response({'available': True, **result})
        return Response({
            'metadata': {}, 'available': False,
            'detail': 'Automatic metadata retrieval is not implemented for this provider. Enter verified values manually.',
        })

    @action(detail=False, methods=['get'], url_path='meta')
    def meta(self, request):
        """Return static metadata: supported providers, capabilities, and model lists."""
        data = {
            'providers': dict(AIProviderConfig.PROVIDER_CHOICES),
            'capabilities': dict(AIProviderConfig.CAPABILITY_CHOICES),
            'models': {
                f'{p}_{c}': models
                for (p, c), models in PROVIDER_MODELS.items()
            },
        }
        return Response(data)

    @action(detail=False, methods=['post'], url_path='fetch-models')
    def fetch_models(self, request):
        """
        Fetch live model list directly from a provider's API.

        Accepts either:
          - {config_id} to load credentials from a saved config, or
          - {provider, capability, api_key} (+optional base_url) for an unsaved config.

        Returns {models: [...], source: 'api'|'fallback'} where 'fallback' means
        the provider doesn't support model listing and the hardcoded list is returned.
        """
        config_id  = request.data.get('config_id')
        provider   = request.data.get('provider', '')
        capability = request.data.get('capability', '')
        api_key    = request.data.get('api_key', '')
        base_url   = request.data.get('base_url', '')

        if config_id:
            try:
                saved = AIProviderConfig.objects.get(pk=config_id)
                provider   = provider   or saved.provider
                capability = capability or saved.capability
                api_key    = api_key    or saved.api_key
                base_url   = base_url   or saved.base_url
            except AIProviderConfig.DoesNotExist:
                return Response({'error': 'Config not found'}, status=status.HTTP_404_NOT_FOUND)

        api_key_required = provider != AIProviderConfig.PROVIDER_LM_STUDIO
        if not provider or not capability or (api_key_required and not api_key):
            return Response(
                {'error': 'provider, capability, and api_key are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temp = AIProviderConfig(
            provider=provider, capability=capability,
            api_key=api_key, model='', base_url=base_url,
        )
        try:
            p = build_provider(temp)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        list_error = ''
        model_metadata = {}
        try:
            detailed_models = getattr(p, 'list_models_with_metadata', None)
            if callable(detailed_models):
                details = detailed_models()
                models = [item['id'] for item in details]
                model_metadata = {item['id']: item for item in details}
            else:
                models = p.list_models()
        except Exception as e:
            logger.warning('list_models failed for %s/%s: %s', provider, capability, e)
            list_error = str(e)
            models = []

        if models:
            return Response({'models': models, 'model_metadata': model_metadata, 'source': 'api'})

        # Provider doesn't expose a models endpoint — return the hardcoded fallback
        fallback = PROVIDER_MODELS.get((provider, capability), [])
        payload = {'models': fallback, 'source': 'fallback'}
        if list_error:
            payload['warning'] = list_error
        return Response(payload)


class KiwiRouterViewSet(viewsets.ModelViewSet):
    queryset = KiwiRouter.objects.prefetch_related('members__provider_config')
    serializer_class = KiwiRouterSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['get'])
    def decisions(self, request, pk=None):
        rows = KiwiRoutingDecision.objects.filter(router_id=pk).select_related('member__provider_config')[:100]
        return Response(KiwiRoutingDecisionSerializer(rows, many=True).data)
