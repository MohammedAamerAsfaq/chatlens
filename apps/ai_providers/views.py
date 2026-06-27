import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import AIProviderConfig
from .serializers import AIProviderConfigSerializer, PROVIDER_MODELS
from .manager import build_provider

logger = logging.getLogger(__name__)


class AIProviderConfigViewSet(viewsets.ModelViewSet):
    queryset = AIProviderConfig.objects.all()
    serializer_class = AIProviderConfigSerializer
    permission_classes = [AllowAny]

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

    @action(detail=True, methods=['post'], url_path='test')
    def test_connection(self, request, pk=None):
        config = self.get_object()
        try:
            result = build_provider(config).test_connection()
        except Exception as e:
            logger.exception('Provider test failed for config %s', pk)
            result = {'ok': False, 'error': str(e)}
        return Response(result)

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

        if not provider or not capability or not api_key:
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

        try:
            models = p.list_models()
        except Exception as e:
            logger.warning('list_models failed for %s/%s: %s', provider, capability, e)
            models = []

        if models:
            return Response({'models': models, 'source': 'api'})

        # Provider doesn't expose a models endpoint — return the hardcoded fallback
        fallback = PROVIDER_MODELS.get((provider, capability), [])
        return Response({'models': fallback, 'source': 'fallback'})
