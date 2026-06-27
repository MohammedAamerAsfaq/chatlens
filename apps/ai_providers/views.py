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
