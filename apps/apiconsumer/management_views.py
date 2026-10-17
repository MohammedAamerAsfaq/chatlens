from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.permissions import CompanyAdminPermission
from apps.tenancy.services.access import default_company_for_user

from .management_serializers import ApiKeyCreatedSerializer, ApiKeyCreateSerializer, ApiKeySerializer
from .models import ApiKey


class ApiKeyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CompanyAdminPermission]
    serializer_class = ApiKeySerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        company = default_company_for_user(self.request.user)
        if company is None:
            return ApiKey.objects.none()
        return ApiKey.objects.filter(company=company)

    def create(self, request, *args, **kwargs):
        company = default_company_for_user(request.user)
        if company is None:
            return Response({'detail': 'No accessible company is selected.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key, secret = ApiKey.generate(
            company=company,
            name=serializer.validated_data['name'],
            scopes=list(serializer.validated_data['scopes']),
            created_by=request.user,
            expires_at=serializer.validated_data.get('expires_at'),
        )
        payload = ApiKeyCreatedSerializer(api_key).data
        payload['secret'] = secret
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        api_key = self.get_object()
        api_key.revoke()
        return Response(ApiKeySerializer(api_key).data)
