import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from .services.ingestion_service import IngestionService
from .services.session_service import SessionService
from .models import WhatsAppAccount, WhatsAppContact, SyncLog

logger = logging.getLogger(__name__)


def _verify_internal_token(request) -> bool:
    token = request.headers.get('X-Internal-Token', '')
    return token == settings.INTERNAL_API_TOKEN


@csrf_exempt
@require_POST
def internal_message_ingest(request):
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    required = ['worker_session_id', 'provider_message_id', 'chat_id', 'direction', 'message_time']
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return JsonResponse({'error': f'Missing fields: {missing}'}, status=400)

    try:
        service = IngestionService()
        message = service.ingest_message(payload)
        return JsonResponse({'success': True, 'message_id': message.id})
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'WhatsApp account not found'}, status=404)
    except Exception as e:
        logger.exception('Error in internal_message_ingest')
        try:
            account = WhatsAppAccount.objects.get(pk=payload.get('worker_session_id'))
            SyncLog.objects.create(
                account=account,
                event_type='message_ingest',
                status='error',
                message=str(e),
                metadata={
                    'provider_message_id': payload.get('provider_message_id'),
                    'chat_id': payload.get('chat_id'),
                    'error': str(e),
                },
            )
        except Exception:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def internal_session_status(request):
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    required = ['worker_session_id', 'status']
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return JsonResponse({'error': f'Missing fields: {missing}'}, status=400)

    try:
        service = SessionService()
        account = service.update_session_status(payload)
        return JsonResponse({'success': True, 'account_id': account.id, 'status': account.session_status})
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'WhatsApp account not found'}, status=404)
    except Exception as e:
        logger.exception('Error in internal_session_status')
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def internal_account_settings(request, session_id):
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        account = WhatsAppAccount.objects.get(pk=session_id)
        return JsonResponse({
            'sync_history': account.sync_history,
            'history_days': account.history_days,
            'idle_disconnect_minutes': account.idle_disconnect_minutes,
            'auto_download_media': account.auto_download_media,
        })
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@csrf_exempt
@require_POST
def internal_contacts_update(request):
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    worker_session_id = payload.get('worker_session_id')
    contacts_data = payload.get('contacts', [])

    if not worker_session_id:
        return JsonResponse({'error': 'Missing worker_session_id'}, status=400)

    try:
        account = WhatsAppAccount.objects.get(pk=worker_session_id)
        updated = 0
        for contact_data in contacts_data:
            wa_contact_id = contact_data.get('wa_contact_id', '')
            push_name = (contact_data.get('push_name') or '').strip()
            if not wa_contact_id or not push_name:
                continue
            phone_from_jid = contact_data.get('phone_number', '')
            is_lid = wa_contact_id.endswith('@lid')

            # Create the contact if it doesn't exist yet (e.g. address-book contacts
            # that have never sent a direct message or group message to this account).
            # On update: refresh push_name (their WA display name may change).
            # On create: also seed display_name and phone_number.
            contact, created = WhatsAppContact.objects.update_or_create(
                account=account,
                wa_contact_id=wa_contact_id,
                defaults={'push_name': push_name},
                create_defaults={
                    'display_name': push_name,
                    'phone_number': phone_from_jid,
                },
            )

            if not created:
                extra = {}
                if not contact.display_name:
                    extra['display_name'] = push_name
                if phone_from_jid:
                    if is_lid or not contact.phone_number:
                        extra['phone_number'] = phone_from_jid
                if extra:
                    WhatsAppContact.objects.filter(pk=contact.pk).update(**extra)

            # Cross-link: when a LID contact has a resolved phone number, also update
            # the phone-JID contact (phone@s.whatsapp.net) with the name.
            # Chats are linked to phone-JID contacts, so without this cross-link
            # the chat list shows the phone number instead of the contact's name.
            if is_lid and phone_from_jid:
                phone_jid = f"{phone_from_jid}@s.whatsapp.net"
                WhatsAppContact.objects.filter(
                    account=account, wa_contact_id=phone_jid
                ).update(push_name=push_name)
                WhatsAppContact.objects.filter(
                    account=account, wa_contact_id=phone_jid, display_name=''
                ).update(display_name=push_name)

            updated += 1
        return JsonResponse({'status': 'ok', 'updated': updated})
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)
    except Exception as e:
        logger.exception('Error in internal_contacts_update')
        return JsonResponse({'error': str(e)}, status=500)
