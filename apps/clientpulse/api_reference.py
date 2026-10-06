import re

from django.db import transaction
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied
from apps.clientpulse.models import ClientPulseSettings, ClientTag
from apps.clientpulse.serializers import ClientPulseSettingsInputSerializer
from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import default_company_for_user


TAG_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _tag_payload(tag):
    usage_count = getattr(tag, 'usage_count', None)
    if usage_count is None:
        usage_count = tag.assignments.count()
    return {
        'id': tag.pk,
        'name': tag.name,
        'color': tag.color,
        'usage_count': usage_count,
    }


def _tag_values(data, *, partial=False, tag=None):
    errors = {}
    raw_name = data.get('name')
    if raw_name is None:
        if not partial:
            errors['name'] = ['This field is required.']
        name = tag.name if tag else ''
    else:
        name = ' '.join(str(raw_name).split())
        if not name:
            errors['name'] = ['This field may not be blank.']
        elif len(name) > 100:
            errors['name'] = ['Ensure this field has no more than 100 characters.']
    color = str(data.get('color', tag.color if tag else '#23865b')).strip()
    if not TAG_COLOR_PATTERN.fullmatch(color):
        errors['color'] = ['Use a six-digit hex color such as #23865b.']
    return name, color.lower(), errors


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_tags_view(request):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.clients.update'
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    if request.method == 'POST':
        name, color, errors = _tag_values(request.data)
        if errors:
            return Response(errors, status=400)
        existing = ClientTag.objects.filter(company=company, normalized_name=name.casefold()).first()
        if existing and existing.is_active:
            return Response({'name': ['This tag already exists.']}, status=400)
        if existing:
            existing.name, existing.color, existing.is_active = name, color, True
            existing.save(update_fields=['name', 'normalized_name', 'color', 'is_active', 'updated_at'])
            tag = existing
        else:
            tag = ClientTag.objects.create(company=company, name=name, color=color)
        return Response(_tag_payload(tag), status=201)
    tags = ClientTag.objects.filter(company=company, is_active=True).annotate(
        usage_count=Count('assignments'),
    )
    return Response([_tag_payload(tag) for tag in tags])


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def client_tag_detail_view(request, tag_id):
    permission = 'clientpulse.clients.view' if request.method == 'GET' else 'clientpulse.clients.update'
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    tag = ClientTag.objects.filter(company=company, is_active=True, pk=tag_id).annotate(
        usage_count=Count('assignments'),
    ).first()
    if not tag:
        return Response({'detail': 'Tag not found.'}, status=404)
    if request.method == 'GET':
        return Response(_tag_payload(tag))
    if request.method == 'PATCH':
        name, color, errors = _tag_values(request.data, partial=True, tag=tag)
        if errors:
            return Response(errors, status=400)
        duplicate = ClientTag.objects.filter(
            company=company, normalized_name=name.casefold(),
        ).exclude(pk=tag.pk).exists()
        if duplicate:
            return Response({'name': ['This tag already exists.']}, status=400)
        tag.name, tag.color = name, color
        tag.save(update_fields=['name', 'normalized_name', 'color', 'updated_at'])
        return Response(_tag_payload(tag))
    with transaction.atomic():
        tag.assignments.all().delete()
        tag.is_active = False
        tag.save(update_fields=['is_active', 'updated_at'])
    return Response(status=204)


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
