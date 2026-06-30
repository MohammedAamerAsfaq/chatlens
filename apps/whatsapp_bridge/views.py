import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from .services.ingestion_service import IngestionService
from .services.session_service import SessionService
from .models import (
    WhatsAppAccount, WhatsAppContact, WhatsAppChat, SyncLog, DroppedMessage,
    WhatsAppGroup, WhatsAppGroupParticipant, ParticipantRole,
)

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
def internal_message_ingest_batch(request):
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    messages = data.get('messages', [])
    if not isinstance(messages, list) or not messages:
        return JsonResponse({'error': 'messages must be a non-empty list'}, status=400)

    try:
        service = IngestionService()
        result = service.ingest_batch(messages)
        return JsonResponse({'success': True, **result})
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'WhatsApp account not found'}, status=404)
    except Exception as e:
        logger.exception('Error in internal_message_ingest_batch')
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

            # LID JIDs must never be primary contact identifiers.
            # The worker sends phone JIDs as wa_contact_id and LIDs as the lid_jid alias.
            if wa_contact_id.endswith('@lid'):
                logger.error(
                    'internal_contacts_update: rejected LID primary %s — '
                    'worker must send phone JID as wa_contact_id with lid_jid as alias',
                    wa_contact_id,
                )
                continue

            phone_number = contact_data.get('phone_number', '')
            lid_jid  = contact_data.get('lid_jid')  or None
            username = contact_data.get('username')  or None

            defaults = {'push_name': push_name}
            if lid_jid:
                defaults['lid_jid'] = lid_jid
            if username:
                defaults['username'] = username

            contact, created = WhatsAppContact.objects.update_or_create(
                account=account,
                wa_contact_id=wa_contact_id,
                defaults=defaults,
                create_defaults={
                    'display_name': push_name,
                    'phone_number': phone_number,
                },
            )

            if not created:
                extra = {}
                if not contact.display_name:
                    extra['display_name'] = push_name
                if phone_number and not contact.phone_number:
                    extra['phone_number'] = phone_number
                if extra:
                    WhatsAppContact.objects.filter(pk=contact.pk).update(**extra)

            updated += 1
        return JsonResponse({'status': 'ok', 'updated': updated})
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)
    except Exception as e:
        logger.exception('Error in internal_contacts_update')
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def internal_group_update(request):
    """Upsert full group metadata + participant list sent from the worker."""
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    worker_session_id = payload.get('worker_session_id')
    group_id = (payload.get('group_id') or '').strip()

    if not worker_session_id or not group_id:
        return JsonResponse({'error': 'Missing worker_session_id or group_id'}, status=400)

    if not group_id.endswith('@g.us'):
        return JsonResponse({'error': f'Invalid group JID: {group_id!r}'}, status=400)

    try:
        account = WhatsAppAccount.objects.get(pk=worker_session_id)
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)

    try:
        community_id_raw = (payload.get('community_id') or '').strip() or None
        community_group = None
        if community_id_raw:
            community_group, _ = WhatsAppGroup.objects.get_or_create(
                account=account,
                wa_group_id=community_id_raw,
                defaults={'is_community': True},
            )

        # Link to WhatsAppChat if one already exists for this group JID
        chat_link = None
        try:
            chat_link = WhatsAppChat.objects.get(account=account, wa_chat_id=group_id)
        except WhatsAppChat.DoesNotExist:
            pass

        group_defaults = {
            'name': (payload.get('name') or '').strip(),
            'description': (payload.get('description') or '').strip(),
            'owner_jid': (payload.get('owner_jid') or '').strip(),
            'is_community': bool(payload.get('is_community', False)),
            'community': community_group,
        }
        if chat_link:
            group_defaults['chat'] = chat_link

        group, _ = WhatsAppGroup.objects.update_or_create(
            account=account,
            wa_group_id=group_id,
            defaults=group_defaults,
        )

        # Upsert full participant list when provided
        participants_data = payload.get('participants') or []
        if participants_data:
            active_jids = set()
            for p in participants_data:
                jid = (p.get('jid') or '').strip()
                if not jid:
                    continue
                role = p.get('role') or ParticipantRole.MEMBER
                if role not in ParticipantRole.values:
                    role = ParticipantRole.MEMBER
                active_jids.add(jid)

                # Resolve contact FK: strip @s.whatsapp.net only
                contact = None
                if jid.endswith('@s.whatsapp.net'):
                    try:
                        contact = WhatsAppContact.objects.get(account=account, wa_contact_id=jid)
                    except WhatsAppContact.DoesNotExist:
                        pass

                WhatsAppGroupParticipant.objects.update_or_create(
                    group=group,
                    wa_jid=jid,
                    defaults={'role': role, 'is_active': True, 'contact': contact},
                )

            # Mark participants not in the latest list as inactive
            WhatsAppGroupParticipant.objects.filter(group=group, is_active=True).exclude(
                wa_jid__in=active_jids
            ).update(is_active=False)

            group.participant_count = len(active_jids)
            group.save(update_fields=['participant_count', 'updated_at'])

        return JsonResponse({'success': True, 'group_id': group.pk})
    except Exception as e:
        logger.exception('Error in internal_group_update')
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def internal_group_participants_update(request):
    """Handle incremental participant change events (add/remove/promote/demote)."""
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    worker_session_id = payload.get('worker_session_id')
    group_id = (payload.get('group_id') or '').strip()
    action = (payload.get('action') or '').strip()
    participant_jids = payload.get('participants') or []

    VALID_ACTIONS = {'add', 'remove', 'promote', 'demote'}
    if not worker_session_id or not group_id or action not in VALID_ACTIONS:
        return JsonResponse(
            {'error': 'Missing/invalid worker_session_id, group_id, or action'}, status=400
        )

    try:
        account = WhatsAppAccount.objects.get(pk=worker_session_id)
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)

    try:
        group = WhatsAppGroup.objects.get(account=account, wa_group_id=group_id)
    except WhatsAppGroup.DoesNotExist:
        # Group metadata not yet synced — create a minimal placeholder
        group = WhatsAppGroup.objects.create(account=account, wa_group_id=group_id)

    try:
        updated = 0
        for jid in participant_jids:
            jid = (jid or '').strip()
            if not jid:
                continue

            contact = None
            if jid.endswith('@s.whatsapp.net'):
                try:
                    contact = WhatsAppContact.objects.get(account=account, wa_contact_id=jid)
                except WhatsAppContact.DoesNotExist:
                    pass

            if action == 'add':
                WhatsAppGroupParticipant.objects.update_or_create(
                    group=group, wa_jid=jid,
                    defaults={'is_active': True, 'role': ParticipantRole.MEMBER, 'contact': contact},
                )
            elif action == 'remove':
                WhatsAppGroupParticipant.objects.filter(group=group, wa_jid=jid).update(is_active=False)
            elif action == 'promote':
                WhatsAppGroupParticipant.objects.update_or_create(
                    group=group, wa_jid=jid,
                    defaults={'role': ParticipantRole.ADMIN, 'is_active': True, 'contact': contact},
                )
            elif action == 'demote':
                WhatsAppGroupParticipant.objects.filter(group=group, wa_jid=jid).update(
                    role=ParticipantRole.MEMBER
                )
            updated += 1

        # Refresh participant count
        active_count = WhatsAppGroupParticipant.objects.filter(group=group, is_active=True).count()
        group.participant_count = active_count
        group.save(update_fields=['participant_count', 'updated_at'])

        return JsonResponse({'success': True, 'updated': updated})
    except Exception as e:
        logger.exception('Error in internal_group_participants_update')
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def internal_dropped_message(request):
    if not _verify_internal_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    worker_session_id = payload.get('worker_session_id')
    if not worker_session_id:
        return JsonResponse({'error': 'Missing worker_session_id'}, status=400)

    try:
        account = WhatsAppAccount.objects.get(pk=worker_session_id)
        DroppedMessage.objects.create(
            account=account,
            msg_id=payload.get('msg_id') or None,
            raw_jid=payload.get('raw_jid') or None,
            from_me=payload.get('from_me'),
            has_message=bool(payload.get('has_message', False)),
            reason=payload.get('reason', 'unknown'),
            raw_key=payload.get('raw_key') or None,
        )
        return JsonResponse({'success': True})
    except WhatsAppAccount.DoesNotExist:
        return JsonResponse({'error': 'Account not found'}, status=404)
    except Exception as e:
        logger.exception('Error in internal_dropped_message')
        return JsonResponse({'error': str(e)}, status=500)
