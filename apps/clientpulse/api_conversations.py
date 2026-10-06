from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clientpulse.api_helpers import denied, profile_or_none
from apps.clientpulse.services.communication_access import visible_clientpulse_accounts
from apps.whatsapp_bridge.models import ChatType, WhatsAppMessage


CONVERSATION_TYPES = {'dm', 'group', 'announcement'}


class ClientConversationPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def _account_payload(account):
    communication = account.communication_account
    return {
        'id': account.pk,
        'name': account.display_name or communication.name or account.phone_number,
        'phone_number': account.phone_number,
        'session_status': account.session_status,
    }


def _message_payload(message):
    account = message.account
    contact = message.chat.contact or message.contact
    group = getattr(message.chat, 'group', None)
    is_announcement = bool(group and (group.announce or group.is_community_announcement))
    return {
        'id': message.pk,
        'account_id': account.pk,
        'account_name': account.display_name or account.communication_account.name or account.phone_number,
        'account_status': account.session_status,
        'chat_id': message.chat_id,
        'contact_id': contact.pk if contact else None,
        'contact_name': (
            (contact.display_name or contact.push_name or contact.phone_number)
            if contact else ''
        ),
        'chat_name': message.chat.name or (group.name if group else '') or message.chat.wa_chat_id,
        'conversation_type': (
            'dm' if message.chat.chat_type == ChatType.INDIVIDUAL
            else 'announcement' if is_announcement else 'group'
        ),
        'direction': message.direction,
        'message_type': message.message_type,
        'message_text': message.message_text,
        'message_time': message.message_time,
        'has_media': message.has_media,
        'media_mime_type': message.media_mime_type,
        'media_file_name': message.media_file_name,
        'media_url': message.media_url,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_conversation_history_view(request, profile_id):
    if response := denied(request, 'clientpulse.clients.view'):
        return response
    profile = profile_or_none(request, profile_id)
    if not profile:
        return Response({'detail': 'Client not found.'}, status=404)
    conversation_type = request.query_params.get('conversation_type', 'dm').strip().lower()
    if conversation_type not in CONVERSATION_TYPES:
        return Response({'conversation_type': ['Choose dm, group, or announcement.']}, status=400)

    visible_accounts = visible_clientpulse_accounts(request.user, profile.company)
    linked_accounts = visible_accounts.filter(
        contacts__company_contact=profile.contact,
    ).select_related('communication_account').distinct().order_by('display_name', 'pk')
    accounts = list(linked_accounts)
    account_id = request.query_params.get('account_id', '').strip()
    if account_id:
        try:
            selected_account_id = int(account_id)
        except ValueError:
            return Response({'account_id': ['A valid account ID is required.']}, status=400)
        if selected_account_id not in {account.pk for account in accounts}:
            return Response({'detail': 'Linked communication account not found.'}, status=404)
        account_ids = [selected_account_id]
    else:
        account_ids = [account.pk for account in accounts]

    messages = WhatsAppMessage.objects.select_related(
        'account__communication_account', 'chat__contact', 'chat__group', 'contact',
    ).filter(
        account_id__in=account_ids,
    )
    if conversation_type == 'dm':
        messages = messages.filter(
            chat__chat_type=ChatType.INDIVIDUAL,
            chat__contact__company_contact=profile.contact,
        )
    else:
        messages = messages.filter(
            chat__chat_type=ChatType.GROUP,
            contact__company_contact=profile.contact,
        )
        announcement = Q(chat__group__announce=True) | Q(
            chat__group__is_community_announcement=True,
        )
        if conversation_type == 'announcement':
            messages = messages.filter(announcement)
        else:
            messages = messages.filter(
                Q(chat__group__isnull=True) | Q(
                    chat__group__announce=False,
                    chat__group__is_community=False,
                    chat__group__is_community_announcement=False,
                ),
            )
    messages = messages.order_by('-message_time', '-pk')
    paginator = ClientConversationPagination()
    page = paginator.paginate_queryset(messages, request)
    response = paginator.get_paginated_response([_message_payload(message) for message in page])
    response.data['accounts'] = [_account_payload(account) for account in accounts]
    return response
