"""Preset reminder actions: everyone who can see reminders reads them, company admins edit them."""
from django.db import transaction
from django.db.models import Max
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied
from apps.clientpulse.models import ClientReminderPhrase
from apps.tenancy.services.access import default_company_for_user

READ_PERMISSION = 'clientpulse.reminders.view'
MANAGE_PERMISSION = 'settings.company.manage'
MAX_LENGTH = ClientReminderPhrase._meta.get_field('text').max_length


def _payload(phrase):
    return {'id': phrase.pk, 'text': phrase.text, 'position': phrase.position}


def _clean_text(data):
    text = ' '.join(str(data.get('text') or '').split())
    if not text:
        return None, {'text': ['Enter the action text.']}
    if len(text) > MAX_LENGTH:
        return None, {'text': [f'Use at most {MAX_LENGTH} characters.']}
    return text, None


def _duplicate(company, text, exclude_pk=None):
    return ClientReminderPhrase.objects.filter(
        company=company, normalized_text=text.casefold(),
    ).exclude(pk=exclude_pk).exists()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reminder_phrases_view(request):
    permission = READ_PERMISSION if request.method == 'GET' else MANAGE_PERMISSION
    if response := denied(request, permission):
        return response
    company = default_company_for_user(request.user)
    phrases = ClientReminderPhrase.objects.filter(company=company)
    if request.method == 'GET':
        return Response([_payload(phrase) for phrase in phrases])
    text, errors = _clean_text(request.data)
    if errors:
        return Response(errors, status=400)
    if _duplicate(company, text):
        return Response({'text': ['This action already exists.']}, status=400)
    last = phrases.aggregate(last=Max('position'))['last']
    phrase = ClientReminderPhrase.objects.create(
        company=company, text=text, position=0 if last is None else last + 1,
    )
    return Response(_payload(phrase), status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def reminder_phrase_detail_view(request, phrase_id):
    if response := denied(request, MANAGE_PERMISSION):
        return response
    company = default_company_for_user(request.user)
    phrase = ClientReminderPhrase.objects.filter(company=company, pk=phrase_id).first()
    if not phrase:
        return Response({'detail': 'Action not found.'}, status=404)
    if request.method == 'DELETE':
        phrase.delete()
        return Response(status=204)
    text, errors = _clean_text(request.data)
    if errors:
        return Response(errors, status=400)
    if _duplicate(company, text, exclude_pk=phrase.pk):
        return Response({'text': ['This action already exists.']}, status=400)
    phrase.text = text
    phrase.save(update_fields=['text', 'normalized_text', 'updated_at'])
    return Response(_payload(phrase))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reorder_reminder_phrases_view(request):
    """Set the dropdown order: `ids` must list every action of the company exactly once."""
    if response := denied(request, MANAGE_PERMISSION):
        return response
    company = default_company_for_user(request.user)
    ids = request.data.get('ids')
    if not isinstance(ids, list) or not all(isinstance(item, int) for item in ids):
        return Response({'ids': ['Send the action ids as a list of numbers.']}, status=400)
    with transaction.atomic():
        phrases = {phrase.pk: phrase for phrase in ClientReminderPhrase.objects.select_for_update().filter(company=company)}
        if len(ids) != len(set(ids)) or set(ids) != set(phrases):
            return Response({'ids': ['The list must contain every action exactly once.']}, status=400)
        for position, pk in enumerate(ids):
            phrases[pk].position = position
        ClientReminderPhrase.objects.bulk_update(phrases.values(), ['position'])
    return Response([_payload(phrases[pk]) for pk in ids])
