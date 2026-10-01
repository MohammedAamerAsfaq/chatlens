from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied
from apps.clientpulse.models import ClientPulseSettings, ClientTag
from apps.clientpulse.serializers import ClientPulseSettingsInputSerializer
from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import default_company_for_user


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_tags_view(request):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.clients.update'
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    if request.method == 'POST':
        name = ' '.join(str(request.data.get('name') or '').split())
        if not name:
            return Response({'name': ['This field is required.']}, status=400)
        if ClientTag.objects.filter(company=company, normalized_name=name.casefold()).exists():
            return Response({'name': ['This tag already exists.']}, status=400)
        tag = ClientTag.objects.create(
            company=company, name=name, color=str(request.data.get('color') or '#23865b'),
        )
        return Response({'id': tag.pk, 'name': tag.name, 'color': tag.color}, status=201)
    return Response([{
        'id': tag.pk, 'name': tag.name, 'color': tag.color,
    } for tag in ClientTag.objects.filter(company=company, is_active=True)])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_options_view(request):
    if response := denied(request, 'clientpulse.clients.view'):
        return response
    company = default_company_for_user(request.user)
    memberships = CompanyMembership.objects.filter(
        company=company, is_active=True,
    ).select_related('user').order_by('user__username')
    return Response({'owners': [{
        'id': item.pk, 'username': item.user.username, 'email': item.user.email,
    } for item in memberships]})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def clientpulse_settings_view(request):
    permission = 'settings.company.view' if request.method == 'GET' else 'settings.company.manage'
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    settings, _ = ClientPulseSettings.objects.get_or_create(company=company)
    if request.method == 'PATCH':
        serializer = ClientPulseSettingsInputSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        for field, value in serializer.validated_data.items():
            setattr(settings, field, value)
        settings.save()
    return Response({
        'automated_follow_up_enabled': settings.automated_follow_up_enabled,
        'consent_mode': settings.consent_mode,
        'reminders_enabled': settings.reminders_enabled,
        'default_timezone': settings.default_timezone,
        'default_language': settings.default_language,
    })
