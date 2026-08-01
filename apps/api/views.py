import io
import json
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from apps.whatsapp_bridge.models import (
    WhatsAppAccount, WhatsAppChat, WhatsAppMessage, WhatsAppContact,
    SyncLog, DroppedMessage, WhatsAppGroup, SessionStatus, WorkerAlert,
    StuckReceipt, WhatsAppUnresolvedMessage, ResolutionStatus, ContactRoleTag,
    BaileysEvent,
)
from apps.tenancy.models import AccountEndpoint, CommunicationAccount, Company, CompanyMembership
from apps.tenancy.services.access import (
    active_membership_for_user,
    available_companies_queryset,
    can_user_access_company,
    default_company_for_user,
    is_control_company_admin,
    scope_queryset_to_visible_accounts,
    visible_companies_queryset,
    visible_accounts_queryset,
)
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService
from apps.tenancy.services.provider_service import ProviderService
from .serializers import (
    WhatsAppAccountSerializer, ChatSerializer, MessageSerializer,
    SyncLogSerializer, DroppedMessageSerializer, ContactDetailSerializer,
    GroupSerializer, GroupDetailSerializer, WorkerAlertSerializer,
    StuckReceiptSerializer, UnresolvedMessageSerializer, BaileysEventSerializer,
)

WORKER_BASE_URL = getattr(settings, 'WORKER_BASE_URL', 'http://localhost:3001')
ACTIVE_COMPANY_SESSION_KEY = 'active_company_id'
logger = logging.getLogger(__name__)


def _company_for_contact(contact):
    communication_account = getattr(contact.account, 'communication_account', None)
    return communication_account.company if communication_account and communication_account.company_id else None


def _contact_roles(contact):
    if hasattr(contact, '_prefetched_objects_cache') and 'role_tags' in contact._prefetched_objects_cache:
        return {tag.role for tag in contact.role_tags.all()}
    return set(contact.role_tags.values_list('role', flat=True))


def _role_category_for_contact(contact):
    roles = _contact_roles(contact)
    if {'supplier', 'customer'}.issubset(roles):
        return 'both'
    if 'supplier' in roles:
        return 'supplier'
    if 'customer' in roles:
        return 'customer'
    return ''


def _set_contact_role_tags(contact, category, source=ContactRoleTag.SOURCE_MANUAL):
    role_map = {
        '': set(),
        None: set(),
        'supplier': {ContactRoleTag.ROLE_SUPPLIER},
        'customer': {ContactRoleTag.ROLE_CUSTOMER},
        'both': {ContactRoleTag.ROLE_SUPPLIER, ContactRoleTag.ROLE_CUSTOMER},
    }
    if category not in role_map:
        raise ValueError('category must be one of supplier, customer, both')

    desired = role_map[category]
    existing = _contact_roles(contact)
    company = _company_for_contact(contact)
    for role in desired - existing:
        ContactRoleTag.objects.get_or_create(
            contact=contact,
            role=role,
            defaults={'company': company, 'source': source},
        )
    if existing - desired:
        contact.role_tags.filter(role__in=existing - desired).delete()
    getattr(contact, '_prefetched_objects_cache', {}).pop('role_tags', None)


def _visible_account_or_none(user, account_id):
    if not account_id:
        return None
    return visible_accounts_queryset(user).filter(pk=account_id).first()


class WhatsAppAccountViewSet(viewsets.ModelViewSet):
    serializer_class = WhatsAppAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return visible_accounts_queryset(
            self.request.user,
            WhatsAppAccount.objects.all().order_by('-created_at'),
        )

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            owner = self.request.user
        else:
            owner = User.objects.filter(is_superuser=True).first()
        with transaction.atomic():
            account = serializer.save(owner=owner)
            company = default_company_for_user(owner)
            if not company:
                logger.warning(
                    'WhatsApp account created without company binding | account_id=%s owner_id=%s',
                    account.pk, owner.pk if owner else None,
                )
                return

            provider = ProviderService().default_provider_for_channel('whatsapp')
            comm_account = CommunicationAccount.objects.create(
                company=company,
                provider=provider,
                channel='whatsapp',
                name=account.display_name or account.phone_number or f'WhatsApp Account #{account.pk}',
                is_active=account.is_active,
                external_account_id=f'whatsapp-account:{account.pk}',
            )
            account.communication_account = comm_account
            update_fields = ['communication_account']
            if account.phone_number:
                endpoint = AccountEndpoint.objects.create(
                    communication_account=comm_account,
                    endpoint_type=AccountEndpoint.TYPE_PHONE,
                    value=account.phone_number,
                    is_primary=True,
                    is_active=account.is_active,
                    metadata={'source': 'api_account_create'},
                )
                account.primary_endpoint = endpoint
                update_fields.append('primary_endpoint')
            account.save(update_fields=update_fields)


    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        # Soft-disconnect from worker (best-effort, don't block delete)
        try:
            requests.post(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/soft-disconnect',
                timeout=5,
            )
        except Exception:
            pass
        account.delete()  # cascades to chats, messages, contacts, sync_logs
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['patch'], url_path='update-settings')
    def update_settings(self, request, pk=None):
        account = self.get_object()
        allowed = ['sync_history', 'history_days', 'idle_disconnect_minutes', 'display_name', 'ai_parsing_enabled', 'auto_download_media']
        update_fields = []
        for field in allowed:
            if field in request.data:
                val = request.data[field]
                # history_days: accept null/None to mean all-time
                if field == 'history_days' and val == '':
                    val = None
                setattr(account, field, val)
                update_fields.append(field)
        if update_fields:
            account.save(update_fields=update_fields)
        return Response(WhatsAppAccountSerializer(account).data)

    @action(detail=True, methods=['get'], url_path='sync-progress')
    def sync_progress(self, request, pk=None):
        from django.utils.timezone import now, timedelta
        from apps.whatsapp_bridge.models import SyncLog
        account = self.get_object()
        since = account.last_connected_at
        if not since:
            return Response({
                'syncing': False, 'total_synced': 0, 'total_processed': 0,
                'batch_count': 0, 'is_complete': False,
                'connection_unhealthy': account.connection_unhealthy,
                'connection_unhealthy_reason': account.connection_unhealthy_reason,
            })

        logs = list(
            SyncLog.objects.filter(
                account=account,
                event_type='history_sync',
                created_at__gte=since,
            ).order_by('created_at').values('metadata', 'created_at')
        )

        total_created = sum(l['metadata'].get('created', 0) for l in logs if l['metadata'])
        total_processed = sum(l['metadata'].get('total', 0) for l in logs if l['metadata'])
        recent_cutoff = now() - timedelta(seconds=30)
        syncing = any(l['created_at'] >= recent_cutoff for l in logs)
        # Authoritative completion signal from Baileys' own isLatest flag — set even
        # when a chunk's messages were entirely filtered out by history_days, so a
        # sync that legitimately finds nothing in the window still reports "done"
        # instead of leaving the UI stuck on "still waiting".
        is_complete = any(l['metadata'].get('is_latest') for l in logs if l['metadata'])
        has_live_messages = SyncLog.objects.filter(
            account=account, event_type='message_ingest', created_at__gte=since,
        ).exists()

        return Response({
            'syncing': syncing,
            'total_synced': total_created,
            'total_processed': total_processed,
            'batch_count': len(logs),
            'has_live_messages': has_live_messages,
            'is_complete': is_complete,
            'connection_unhealthy': account.connection_unhealthy,
            'connection_unhealthy_reason': account.connection_unhealthy_reason,
        })

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        account = self.get_object()

        def generate():
            yield '{"account_id":' + str(account.pk) + ','
            yield '"phone_number":' + json.dumps(account.phone_number) + ','
            yield '"display_name":' + json.dumps(account.display_name) + ','
            yield '"chats":['
            chats = list(account.chats.order_by('created_at'))
            for chat_idx, chat in enumerate(chats):
                msgs = list(
                    chat.messages.order_by('message_time').values(
                        'provider_message_id', 'sender_number', 'direction',
                        'message_type', 'message_text', 'message_time',
                        'has_media', 'media_mime_type', 'media_file_name', 'media_url',
                    )
                )
                chat_obj = {
                    'wa_chat_id': chat.wa_chat_id,
                    'chat_type': chat.chat_type,
                    'name': chat.name,
                    'messages': msgs,
                }
                yield json.dumps(chat_obj, cls=DjangoJSONEncoder)
                if chat_idx < len(chats) - 1:
                    yield ','
            yield ']}'

        resp = StreamingHttpResponse(generate(), content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="chatlens-{account.pk}.json"'
        return resp

    @action(detail=True, methods=['get'])
    def storage(self, request, pk=None):
        account = self.get_object()
        message_count = WhatsAppMessage.objects.filter(chat__account=account).count()
        media_message_count = WhatsAppMessage.objects.filter(chat__account=account, has_media=True).count()
        chat_count = account.chats.count()
        contact_count = WhatsAppContact.objects.filter(account=account).count()
        sync_log_count = SyncLog.objects.filter(account=account).count()

        media_stats = {'file_count': 0, 'total_bytes': 0, 'error': None}
        try:
            resp = requests.get(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/storage',
                timeout=10,
            )
            if resp.status_code == 200:
                media_stats = resp.json()
            else:
                media_stats['error'] = f'Worker returned {resp.status_code}'
        except Exception as e:
            media_stats['error'] = str(e)

        return Response({
            'account_id': account.pk,
            'display_name': account.display_name,
            'phone_number': account.phone_number,
            'session_status': account.session_status,
            'db': {
                'message_count': message_count,
                'media_message_count': media_message_count,
                'chat_count': chat_count,
                'contact_count': contact_count,
                'sync_log_count': sync_log_count,
            },
            'media': media_stats,
        })

    # ------------------------------------------------------------------ #
    #  Message management                                                 #
    # ------------------------------------------------------------------ #

    @action(detail=True, methods=['post'], url_path='delete-messages')
    def delete_messages(self, request, pk=None):
        account = self.get_object()
        deleted, _ = WhatsAppMessage.objects.filter(chat__account=account).delete()
        account.chats.update(unread_count=0, last_message_at=None)
        return Response({'deleted': deleted})

    @action(detail=True, methods=['post'], url_path='set-auto-download')
    def set_auto_download(self, request, pk=None):
        account = self.get_object()
        enabled = request.data.get('enabled')
        if not isinstance(enabled, bool):
            return Response({'error': 'enabled must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)
        account.auto_download_media = enabled
        account.save(update_fields=['auto_download_media'])
        return Response({'id': account.pk, 'auto_download_media': account.auto_download_media})

    @action(detail=False, methods=['post'], url_path='set-auto-download-all')
    def set_auto_download_all(self, request):
        enabled = request.data.get('enabled')
        if not isinstance(enabled, bool):
            return Response({'error': 'enabled must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)
        self.get_queryset().update(auto_download_media=enabled)
        return Response({'enabled': enabled})

    @action(detail=True, methods=['get', 'delete'], url_path='message-logs')
    def message_logs(self, request, pk=None):
        account = self.get_object()
        if request.method == 'DELETE':
            try:
                requests.delete(
                    f'{WORKER_BASE_URL}/sessions/{account.pk}/message-logs',
                    timeout=10,
                )
            except Exception:
                pass
            return Response({'ok': True})
        params = request.query_params.dict()
        try:
            resp = requests.get(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/message-logs',
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            return Response(resp.json())
        except Exception as e:
            return Response({'count': 0, 'results': [], 'error': str(e)})

    @action(detail=False, methods=['post'], url_path='delete-all-messages')
    def delete_all_messages(self, request):
        visible_accounts = self.get_queryset()
        deleted, _ = WhatsAppMessage.objects.filter(chat__account__in=visible_accounts).delete()
        WhatsAppChat.objects.filter(account__in=visible_accounts).update(unread_count=0, last_message_at=None)
        return Response({'deleted': deleted})

    # ------------------------------------------------------------------ #
    #  Media management                                                    #
    # ------------------------------------------------------------------ #

    @action(detail=True, methods=['post'], url_path='delete-media')
    def delete_media(self, request, pk=None):
        account = self.get_object()
        media_dir = Path(settings.WORKER_MEDIA_PATH) / str(account.pk)
        removed_bytes = 0
        removed_files = 0
        if media_dir.exists():
            for f in media_dir.rglob('*'):
                if f.is_file():
                    removed_bytes += f.stat().st_size
                    removed_files += 1
            shutil.rmtree(media_dir)
        # Clear media_url references in DB
        WhatsAppMessage.objects.filter(chat__account=account, has_media=True).update(media_url='')
        return Response({'removed_files': removed_files, 'removed_bytes': removed_bytes})

    @action(detail=False, methods=['post'], url_path='delete-all-media')
    def delete_all_media(self, request):
        visible_account_ids = list(self.get_queryset().values_list('pk', flat=True))
        media_root = Path(settings.WORKER_MEDIA_PATH)
        removed_bytes = 0
        removed_files = 0
        for account_id in visible_account_ids:
            media_dir = media_root / str(account_id)
            if not media_dir.exists():
                continue
            for f in media_dir.rglob('*'):
                if f.is_file():
                    removed_bytes += f.stat().st_size
                    removed_files += 1
            shutil.rmtree(media_dir)
        if media_root.exists():
            media_root.mkdir(parents=True, exist_ok=True)
        WhatsAppMessage.objects.filter(chat__account_id__in=visible_account_ids, has_media=True).update(media_url='')
        return Response({'removed_files': removed_files, 'removed_bytes': removed_bytes})

    # ------------------------------------------------------------------ #
    #  Backup                                                              #
    # ------------------------------------------------------------------ #

    @action(detail=True, methods=['get'], url_path='backup-media')
    def backup_media(self, request, pk=None):
        account = self.get_object()
        media_dir = Path(settings.WORKER_MEDIA_PATH) / str(account.pk)

        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
        os.close(tmp_fd)
        try:
            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                if media_dir.exists():
                    for f in sorted(media_dir.rglob('*')):
                        if f.is_file():
                            zf.write(f, f.name)

            def _stream(path):
                try:
                    with open(path, 'rb') as fh:
                        while chunk := fh.read(65536):
                            yield chunk
                finally:
                    os.unlink(path)

            resp = StreamingHttpResponse(_stream(tmp_path), content_type='application/zip')
            resp['Content-Disposition'] = f'attachment; filename="chatlens-media-{account.pk}.zip"'
            return resp
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # ------------------------------------------------------------------ #
    #  Restore                                                             #
    # ------------------------------------------------------------------ #

    @action(detail=True, methods=['post'], url_path='restore-messages')
    def restore_messages(self, request, pk=None):
        account = self.get_object()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = json.load(upload)
        except Exception as e:
            return Response({'error': f'Invalid JSON: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        restored_chats = 0
        restored_messages = 0
        skipped_existing = 0
        invalid_rows = 0

        for chat_data in data.get('chats', []):
            chat, created = WhatsAppChat.objects.get_or_create(
                account=account,
                wa_chat_id=chat_data['wa_chat_id'],
                defaults={
                    'chat_type': chat_data.get('chat_type', 'individual'),
                    'name': chat_data.get('name', ''),
                },
            )
            if created:
                restored_chats += 1

            messages = chat_data.get('messages', [])
            incoming_ids = [
                msg.get('provider_message_id')
                for msg in messages
                if msg.get('provider_message_id')
            ]
            existing_ids = set(
                WhatsAppMessage.objects.filter(
                    account=account,
                    provider_message_id__in=incoming_ids,
                ).values_list('provider_message_id', flat=True)
            )

            seen_ids = set()
            to_create = []
            for msg in messages:
                pid = msg.get('provider_message_id')
                if not pid:
                    invalid_rows += 1
                    continue
                if pid in existing_ids or pid in seen_ids:
                    skipped_existing += 1
                    continue
                seen_ids.add(pid)
                mt = parse_datetime(str(msg['message_time'])) if msg.get('message_time') else None
                if mt is None:
                    invalid_rows += 1
                    continue
                to_create.append(WhatsAppMessage(
                    account=account,
                    chat=chat,
                    provider_message_id=pid,
                    sender_number=msg.get('sender_number', ''),
                    direction=msg.get('direction', 'inbound'),
                    message_type=msg.get('message_type', 'text'),
                    message_text=msg.get('message_text', ''),
                    message_time=mt,
                    has_media=msg.get('has_media', False),
                    media_mime_type=msg.get('media_mime_type', ''),
                    media_file_name=msg.get('media_file_name', ''),
                    media_url=msg.get('media_url', ''),
                ))

            if to_create:
                WhatsAppMessage.objects.bulk_create(to_create)
                restored_messages += len(to_create)

            # Refresh chat timestamps
            latest = chat.messages.order_by('-message_time').first()
            if latest:
                chat.last_message_at = latest.message_time
                chat.save(update_fields=['last_message_at'])

        return Response({
            'restored_chats': restored_chats,
            'restored_messages': restored_messages,
            'skipped_existing': skipped_existing,
            'invalid_rows': invalid_rows,
        })

    @action(detail=True, methods=['post'], url_path='restore-media')
    def restore_media(self, request, pk=None):
        account = self.get_object()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        media_dir = Path(settings.WORKER_MEDIA_PATH) / str(account.pk)
        media_dir.mkdir(parents=True, exist_ok=True)

        ALLOWED_EXT = {
            '.jpg', '.jpeg', '.png', '.webp', '.gif',
            '.mp4', '.3gp', '.mpeg', '.ogg', '.mp3', '.m4a', '.aac',
            '.pdf', '.docx', '.xlsx', '.zip',
        }
        extracted = 0
        skipped = 0

        try:
            with zipfile.ZipFile(upload) as zf:
                for member in zf.namelist():
                    member_name = Path(member).name
                    if not member_name:
                        continue
                    ext = Path(member_name).suffix.lower()
                    if ext not in ALLOWED_EXT:
                        skipped += 1
                        continue
                    dest = media_dir / member_name
                    # Security: only write inside media_dir
                    if not str(dest.resolve()).startswith(str(media_dir.resolve())):
                        skipped += 1
                        continue
                    with zf.open(member) as src, open(dest, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    extracted += 1
        except zipfile.BadZipFile:
            return Response({'error': 'Invalid ZIP file'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'extracted': extracted, 'skipped': skipped})

    @action(detail=True, methods=['post'], url_path='start-session')
    def start_session(self, request, pk=None):
        account = self.get_object()
        try:
            resp = requests.post(
                f'{WORKER_BASE_URL}/sessions',
                json={
                    'session_id': str(account.pk),
                    'sync_history': account.sync_history,
                    'history_days': account.history_days,
                    'idle_disconnect_minutes': account.idle_disconnect_minutes,
                    'auto_download_media': account.auto_download_media,
                },
                timeout=10,
            )
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=['get'])
    def qr(self, request, pk=None):
        account = self.get_object()
        try:
            resp = requests.get(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/qr',
                timeout=10,
            )
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        account = self.get_object()
        try:
            resp = requests.post(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/disconnect',
                timeout=10,
            )
            # The worker is the source of truth for whether a session actually exists —
            # if it says "not found", our stored status is stale (e.g. the worker already
            # cleared credentials after a WhatsApp-side logout, or restarted and never
            # restored this session) and must not be left claiming "connected" with a
            # Disconnect button that can never succeed. Bring the DB in line with what the
            # worker just told us, rather than only updating it when the worker proactively
            # calls back — that callback can be missed (a crash, a dropped request) and
            # nothing here currently notices when it is.
            if resp.status_code == 404 and account.session_status not in (
                SessionStatus.LOGGED_OUT, SessionStatus.DISCONNECTED,
            ):
                account.session_status = SessionStatus.DISCONNECTED
                account.last_disconnected_at = now()
                account.save(update_fields=['session_status', 'last_disconnected_at', 'updated_at'])
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=['post'], url_path='soft-disconnect')
    def soft_disconnect(self, request, pk=None):
        """Ends the socket without a WhatsApp-side logout — credentials on disk are
        left untouched and the worker suppresses its own auto-reconnect, so a later
        Connect reuses the existing session instead of requiring a fresh QR scan.
        Distinct from disconnect() above, which calls sock.logout() and revokes the
        linked device entirely."""
        account = self.get_object()
        try:
            resp = requests.post(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/soft-disconnect',
                timeout=10,
            )
            if resp.status_code == 404 and account.session_status not in (
                SessionStatus.LOGGED_OUT, SessionStatus.DISCONNECTED,
            ):
                account.session_status = SessionStatus.DISCONNECTED
                account.last_disconnected_at = now()
                account.save(update_fields=['session_status', 'last_disconnected_at', 'updated_at'])
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class ChatViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            WhatsAppChat.objects.select_related('contact').order_by('-last_message_at'),
            self.request.user,
        )
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(contact__display_name__icontains=search) |
                Q(contact__phone_number__icontains=search) |
                Q(wa_chat_id__icontains=search)
            )
        return qs

    @action(detail=True, methods=['get'])
    def info(self, request, pk=None):
        from django.db.models import Count, Min, Max
        chat = self.get_object()
        agg = chat.messages.aggregate(
            total=Count('id'),
            first_at=Min('message_time'),
            last_at=Max('message_time'),
        )
        media_counts = {
            mt: chat.messages.filter(message_type=mt).count()
            for mt in ('image', 'video', 'audio', 'document', 'sticker')
        }
        media_counts['total'] = sum(media_counts.values())

        contact_data = None
        if chat.contact:
            contact_data = {
                'display_name': chat.contact.display_name,
                'push_name': chat.contact.push_name,
                'phone_number': chat.contact.phone_number,
                'is_business': chat.contact.is_business,
                'wa_contact_id': chat.contact.wa_contact_id,
            }

        return Response({
            'id': chat.id,
            'wa_chat_id': chat.wa_chat_id,
            'chat_type': chat.chat_type,
            'display_name': ChatSerializer(chat, context=self.get_serializer_context()).data['display_name'],
            'name': chat.name,
            'message_count': agg['total'] or 0,
            'first_message_at': agg['first_at'],
            'last_message_at': agg['last_at'],
            'media_counts': media_counts,
            'contact': contact_data,
        })

    @action(detail=True, methods=['get'], url_path='group-info')
    def group_info(self, request, pk=None):
        from django.db.models import Count, Max
        chat = self.get_object()
        if not chat.wa_chat_id.endswith('@g.us'):
            return Response({'error': 'Not a group chat'}, status=status.HTTP_400_BAD_REQUEST)

        account = chat.account
        description = ''
        member_count = 0
        announce = False
        # LID JIDs of admins/superadmins from live metadata (used for admin badge)
        admin_lids = set()
        super_admin_lids = set()

        # Fetch live metadata for description, count, and admin list.
        # groupMetadata() returns @lid JIDs on linked devices — we DON'T use the
        # participant list for display; we only use it for admin status + metadata.
        try:
            resp = requests.get(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/groups/{chat.wa_chat_id}',
                timeout=15,
            )
            if resp.status_code == 200:
                meta = resp.json()
                description = meta.get('desc') or ''
                announce = meta.get('announce', False)
                raw_parts = meta.get('participants', [])
                member_count = len(raw_parts)
                admin_lids = {p['id'] for p in raw_parts if p.get('isAdmin')}
                super_admin_lids = {p['id'] for p in raw_parts if p.get('isSuperAdmin')}
        except Exception:
            pass

        # Build participant list from message history.
        # Group messages always carry the sender's real phone JID in msg.key.participant,
        # so sender_number in WhatsAppMessage is a real phone number regardless of LID mode.
        sender_rows = (
            chat.messages
            .exclude(sender_number='')
            .values('sender_number')
            .annotate(msg_count=Count('id'), last_msg=Max('message_time'))
            .order_by('-msg_count')
        )

        sender_phones = [r['sender_number'] for r in sender_rows]
        phone_jids = [f"{ph}@s.whatsapp.net" for ph in sender_phones]

        # Look up names from contacts table by phone JID
        contacts_map = {
            c['wa_contact_id']: c
            for c in WhatsAppContact.objects.filter(
                account=account, wa_contact_id__in=phone_jids,
            ).values('wa_contact_id', 'display_name', 'push_name', 'phone_number')
        }

        # Reverse-map phone → admin LID so we can mark admins from the metadata list
        # (requires contacts to have their phone_number resolved from LID mapping)
        phone_to_lid = {}
        if admin_lids or super_admin_lids:
            for c in WhatsAppContact.objects.filter(
                account=account,
                wa_contact_id__in=list(admin_lids | super_admin_lids),
                phone_number__gt='',
            ).values('wa_contact_id', 'phone_number'):
                phone_to_lid[c['phone_number']] = c['wa_contact_id']

        participants = []
        for r in sender_rows:
            phone = r['sender_number']
            jid = f"{phone}@s.whatsapp.net"
            c = contacts_map.get(jid, {})
            lid = phone_to_lid.get(phone, '')
            participants.append({
                'jid': jid,
                'phone': phone,
                'display_name': c.get('display_name') or c.get('push_name') or '',
                'is_admin': lid in admin_lids,
                'is_super_admin': lid in super_admin_lids,
            })

        participants.sort(key=lambda p: (
            0 if p['is_super_admin'] else 1 if p['is_admin'] else 2,
            (p['display_name'] or p['phone'] or '').lower(),
        ))

        return Response({
            'description': description,
            'member_count': member_count or len(participants),
            'announce': announce,
            'participants': participants,
            'active_senders': len(participants),
        })

    @action(detail=True, methods=['patch'], url_path='set-ai-parsing')
    def set_ai_parsing(self, request, pk=None):
        chat = self.get_object()
        val = request.data.get('ai_parsing', 'inherit')
        if val in (True, 'true', '1', 1):
            chat.ai_parsing = True
        elif val in (False, 'false', '0', 0):
            chat.ai_parsing = False
        else:
            chat.ai_parsing = None  # inherit from account
        chat.save(update_fields=['ai_parsing'])
        return Response(ChatSerializer(chat, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        chat = self.get_object()
        chat.unread_count = 0
        chat.save(update_fields=['unread_count'])
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        account_id = request.query_params.get('account')
        qs = scope_queryset_to_visible_accounts(WhatsAppChat.objects.all(), request.user)
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        qs.update(unread_count=0)
        return Response({'status': 'ok'})

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        chat = self.get_object()
        limit = min(int(request.query_params.get('limit', 40)), 100)
        before = request.query_params.get('before')  # cursor: load older messages
        after  = request.query_params.get('after')   # cursor: load newer messages (polling)

        qs = chat.messages.select_related('contact')

        if after:
            # Polling path — return messages newer than cursor, oldest-first
            msgs = list(qs.filter(message_time__gt=after).order_by('message_time')[:limit])
            return Response({'results': MessageSerializer(msgs, many=True).data, 'has_more': False})

        # Initial load / load-older path — newest first, then reverse for display
        qs = qs.order_by('-message_time')
        if before:
            qs = qs.filter(message_time__lt=before)

        rows = list(qs[:limit + 1])
        has_more = len(rows) > limit
        msgs = list(reversed(rows[:limit]))
        return Response({'results': MessageSerializer(msgs, many=True).data, 'has_more': has_more})


class ActivityPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            SyncLog.objects.select_related('account').order_by('-created_at'),
            self.request.user,
        )
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)
        log_status = self.request.query_params.get('status')
        if log_status:
            qs = qs.filter(status=log_status)
        message_id = self.request.query_params.get('message_id')
        if message_id:
            qs = qs.filter(metadata__provider_message_id=message_id)
        return qs

    @action(detail=False, methods=['post'], url_path='clear-all')
    def clear_all(self, request):
        qs = scope_queryset_to_visible_accounts(SyncLog.objects.all(), request.user)
        account_id = request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        deleted, _ = qs.delete()
        return Response({'deleted': deleted})


class DroppedMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DroppedMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            DroppedMessage.objects.select_related('account').order_by('-created_at'),
            self.request.user,
        )
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        reason = self.request.query_params.get('reason')
        if reason:
            qs = qs.filter(reason=reason)
        return qs

    @action(detail=False, methods=['post'], url_path='clear-all')
    def clear_all(self, request):
        qs = scope_queryset_to_visible_accounts(DroppedMessage.objects.all(), request.user)
        account_id = request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        deleted, _ = qs.delete()
        return Response({'deleted': deleted})


class WorkerAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """Structured, queryable record of worker-side failures that would otherwise
    only exist in a raw log file — see WorkerAlert model docstring."""
    serializer_class = WorkerAlertSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            WorkerAlert.objects.select_related('account').order_by('-created_at'),
            self.request.user,
        )
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            qs = qs.filter(alert_type=alert_type)
        acknowledged = self.request.query_params.get('acknowledged')
        if acknowledged == 'true':
            qs = qs.filter(acknowledged_at__isnull=False)
        elif acknowledged == 'false':
            qs = qs.filter(acknowledged_at__isnull=True)
        return qs

    @action(detail=False, methods=['get'], url_path='unacknowledged-count')
    def unacknowledged_count(self, request):
        qs = scope_queryset_to_visible_accounts(
            WorkerAlert.objects.filter(acknowledged_at__isnull=True),
            request.user,
        )
        return Response({'count': qs.count()})

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged_at = now()
        alert.acknowledged_by = request.user if request.user.is_authenticated else None
        alert.save(update_fields=['acknowledged_at', 'acknowledged_by'])
        return Response(WorkerAlertSerializer(alert).data)

    @action(detail=False, methods=['post'], url_path='acknowledge-all')
    def acknowledge_all(self, request):
        qs = scope_queryset_to_visible_accounts(
            WorkerAlert.objects.filter(acknowledged_at__isnull=True),
            request.user,
        )
        account_id = request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        updated = qs.update(acknowledged_at=now(), acknowledged_by=request.user if request.user.is_authenticated else None)
        return Response({'acknowledged': updated})


class BaileysEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Per-message Baileys audit trail for both successful and failed worker
    decisions. This is intentionally read-only from the UI; writes come only
    from the internal worker endpoint."""
    serializer_class = BaileysEventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            BaileysEvent.objects.select_related('account', 'whatsapp_message').order_by('-created_at'),
            self.request.user,
            account_field='account',
        )
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        event_stage = self.request.query_params.get('event_stage')
        if event_stage:
            qs = qs.filter(event_stage=event_stage)
        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        reason = self.request.query_params.get('reason')
        if reason:
            qs = qs.filter(reason=reason)
        provider_message_id = self.request.query_params.get('provider_message_id')
        if provider_message_id:
            qs = qs.filter(provider_message_id=provider_message_id)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(provider_message_id__icontains=search)
                | Q(raw_jid__icontains=search)
                | Q(remote_jid__icontains=search)
                | Q(participant_jid__icontains=search)
                | Q(participant_pn__icontains=search)
                | Q(sender_jid__icontains=search)
                | Q(sender_number__icontains=search)
                | Q(push_name__icontains=search)
                | Q(reason__icontains=search)
                | Q(error_message__icontains=search)
            )
        return qs


class StuckReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """Messages WhatsApp keeps asking us to resend that our own send path can't
    fulfill — see StuckReceipt model docstring. Resolving one here is just a
    review/audit marker; it does not affect the worker's in-memory skip-list
    (that's keyed off the row's mere existence, not its resolved_at)."""
    serializer_class = StuckReceiptSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            StuckReceipt.objects.select_related('account').order_by('-last_seen_at'),
            self.request.user,
            account_field='account',
        )
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        resolved = self.request.query_params.get('resolved')
        if resolved == 'true':
            qs = qs.filter(resolved_at__isnull=False)
        elif resolved == 'false':
            qs = qs.filter(resolved_at__isnull=True)
        return qs

    @action(detail=False, methods=['get'], url_path='unresolved-count')
    def unresolved_count(self, request):
        qs = scope_queryset_to_visible_accounts(
            StuckReceipt.objects.filter(resolved_at__isnull=True),
            request.user,
            account_field='account',
        )
        return Response({'count': qs.count()})

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        receipt = self.get_object()
        receipt.resolved_at = now()
        receipt.resolved_by = request.user if request.user.is_authenticated else None
        receipt.save(update_fields=['resolved_at', 'resolved_by'])
        return Response(StuckReceiptSerializer(receipt).data)


class UnresolvedMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Observability for WhatsAppUnresolvedMessage — messages preserved with real
    content whose LID couldn't be resolved to a phone JID at ingestion time.
    Resolution happens automatically (see IngestionService.recover_unresolved_for_lid,
    triggered from internal_contacts_update whenever a LID→phone mapping becomes
    known) — this viewset is read-only, purely for audit visibility. See
    'docs/Contact Message Loss — LID Resolution Fix Proposal.md'."""
    serializer_class = UnresolvedMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = (
            WhatsAppUnresolvedMessage.objects
            .select_related('account', 'resolved_contact', 'resolved_message')
            .order_by('-created_at')
        )
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='account')
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))
        resolution_status = self.request.query_params.get('resolution_status')
        if resolution_status:
            qs = qs.filter(resolution_status=resolution_status)
        return qs

    @action(detail=False, methods=['get'], url_path='counts')
    def counts(self, request):
        qs = scope_queryset_to_visible_accounts(
            WhatsAppUnresolvedMessage.objects.all(),
            request.user,
            account_field='account',
        )
        account_id = request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        return Response({
            'pending':  qs.filter(resolution_status=ResolutionStatus.PENDING).count(),
            'resolved': qs.filter(resolution_status=ResolutionStatus.RESOLVED).count(),
            'failed':   qs.filter(resolution_status=ResolutionStatus.FAILED).count(),
        })


class ContactViewSet(viewsets.ModelViewSet):
    serializer_class = ContactDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination
    http_method_names = ['get', 'patch', 'head', 'options']

    ORDERING_FIELDS = {
        'display_name':  ['display_name', 'push_name', 'phone_number'],
        'push_name':     ['push_name', 'display_name'],
        'phone_number':  ['phone_number'],
        'category':      ['category', 'display_name'],
        'message_count': ['message_count'],
    }

    def get_queryset(self):
        qs = (
            WhatsAppContact.objects
            .select_related('account')
            .prefetch_related('chats', 'role_tags')
            .annotate(message_count=Count('messages', distinct=True))
        )
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='account')

        ordering = self.request.query_params.get('ordering') or 'display_name'
        descending = ordering.startswith('-')
        field = ordering[1:] if descending else ordering
        order_fields = self.ORDERING_FIELDS.get(field, self.ORDERING_FIELDS['display_name'])
        if descending:
            order_fields = [f'-{f}' for f in order_fields]
        qs = qs.order_by(*order_fields)

        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))

        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(display_name__icontains=search) |
                Q(push_name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(wa_contact_id__icontains=search)
            )

        contact_type = self.request.query_params.get('type')
        if contact_type == 'phone':
            qs = qs.filter(wa_contact_id__endswith='@s.whatsapp.net')
        elif contact_type == 'lid':
            qs = qs.filter(wa_contact_id__endswith='@lid')
        elif contact_type == 'group':
            qs = qs.filter(wa_contact_id__endswith='@g.us')

        category = self.request.query_params.get('category')
        if category is not None:
            if category == 'both':
                qs = qs.filter(role_tags__role='supplier').filter(role_tags__role='customer')
            elif category in ('supplier', 'customer'):
                qs = qs.filter(role_tags__role=category)
            elif category in ('', 'none'):
                qs = qs.exclude(role_tags__role__in=['supplier', 'customer'])

        return qs

    def partial_update(self, request, *args, **kwargs):
        contact = self.get_object()
        category = request.data.get('category', contact.category)
        if 'category' in request.data:
            try:
                _set_contact_role_tags(contact, category, source=ContactRoleTag.SOURCE_MANUAL)
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Only display_name and category are user-editable; category now writes role tags
        # while the legacy column stays synchronized for backward compatibility.
        data = {
            'display_name': request.data.get('display_name', contact.display_name),
            'category': category,
        }
        serializer = self.get_serializer(contact, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='confirm-category')
    def confirm_category(self, request, pk=None):
        """Applies a category the user accepted from an inquiry's "AI suggests..."
        button — distinct from partial_update (the Contacts page's deliberate manual
        edit) because this value can be stale: it was computed from the contact's
        category at classification time, and a *different* inquiry from the same
        contact may have already moved it to "both" since then (nothing retroactively
        clears an older inquiry's stored suggestion). "both" is a final state (see
        validate_category_suggestion), so if the contact is already "both" by the
        time this save actually runs, the incoming value is silently ignored rather
        than letting a stale click downgrade it back to "supplier"/"customer".
        """
        contact = self.get_object()
        category = request.data.get('category')
        if category not in ('supplier', 'customer', 'both'):
            return Response({'detail': 'category must be one of supplier, customer, both'}, status=status.HTTP_400_BAD_REQUEST)

        desired = {'supplier', 'customer'} if category == 'both' else {category}
        roles = _contact_roles(contact)
        company = _company_for_contact(contact)
        for role in desired - roles:
            ContactRoleTag.objects.get_or_create(
                contact=contact,
                role=role,
                defaults={'company': company, 'source': ContactRoleTag.SOURCE_AI_SUGGESTION},
            )
        final_roles = roles | desired
        if {'supplier', 'customer'}.issubset(final_roles):
            contact.category = 'both'
        elif 'supplier' in final_roles:
            contact.category = 'supplier'
        elif 'customer' in final_roles:
            contact.category = 'customer'
        else:
            contact.category = ''
        getattr(contact, '_prefetched_objects_cache', {}).pop('role_tags', None)
        contact.save(update_fields=['category', 'updated_at'])
        return Response(self.get_serializer(contact).data)

    @action(detail=True, methods=['patch'], url_path='set-ai-parsing')
    def set_ai_parsing(self, request, pk=None):
        contact = self.get_object()
        chat = contact.chats.first()
        if not chat:
            return Response({'detail': 'No chat found for this contact'}, status=status.HTTP_404_NOT_FOUND)
        val = request.data.get('ai_parsing', 'inherit')
        if val in (True, 'true', '1', 1):
            chat.ai_parsing = True
        elif val in (False, 'false', '0', 0):
            chat.ai_parsing = False
        else:
            chat.ai_parsing = None
        chat.save(update_fields=['ai_parsing'])
        contact.refresh_from_db()
        return Response(self.get_serializer(contact).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        account_id = request.query_params.get('account')
        qs = scope_queryset_to_visible_accounts(WhatsAppContact.objects.all(), request.user, account_field='account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        return Response({
            'total':    qs.count(),
            'phone':    qs.filter(wa_contact_id__endswith='@s.whatsapp.net').count(),
            'lid':      qs.filter(wa_contact_id__endswith='@lid').count(),
            'group':    qs.filter(wa_contact_id__endswith='@g.us').count(),
            'username': qs.filter(username__isnull=False).exclude(username='').count(),
        })


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GroupDetailSerializer
        return GroupSerializer

    def get_queryset(self):
        qs = scope_queryset_to_visible_accounts(
            WhatsAppGroup.objects.select_related('account', 'community').order_by('-updated_at'),
            self.request.user,
            account_field='account',
        )

        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(self.request.user, account_id))

        group_type = self.request.query_params.get('type')
        if group_type == 'community':
            qs = qs.filter(is_community=True)
        elif group_type == 'group':
            qs = qs.filter(is_community=False)

        community_id = self.request.query_params.get('community')
        if community_id:
            qs = qs.filter(community_id=community_id)

        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(wa_group_id__icontains=search))

        return qs

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        account_id = request.query_params.get('account')
        qs = scope_queryset_to_visible_accounts(WhatsAppGroup.objects.all(), request.user, account_field='account')
        if account_id:
            qs = qs.filter(account=_visible_account_or_none(request.user, account_id))
        return Response({
            'total':       qs.count(),
            'communities': qs.filter(is_community=True).count(),
            'groups':      qs.filter(is_community=False).count(),
        })

    @action(detail=False, methods=['post'], url_path='sync')
    def sync(self, request):
        """Trigger groupFetchAllParticipating() on the worker for a given account."""
        account_id = request.data.get('account')
        if not account_id:
            return Response({'error': 'account is required'}, status=status.HTTP_400_BAD_REQUEST)
        account = _visible_account_or_none(request.user, account_id)
        if not account:
            return Response({'error': 'Account not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            resp = requests.post(
                f'{WORKER_BASE_URL}/sessions/{account.pk}/sync-groups',
                timeout=60,
            )
            if resp.status_code == 404:
                return Response(
                    {'error': 'Session not connected — connect the WhatsApp session first'},
                    status=status.HTTP_409_CONFLICT,
                )
            resp.raise_for_status()
            return Response(resp.json())
        except requests.RequestException as e:
            return Response({'error': f'Worker unreachable: {e}'}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=['patch'], url_path='set-ai-parsing')
    def set_ai_parsing(self, request, pk=None):
        group = self.get_object()
        chat = WhatsAppChat.objects.filter(account=group.account, wa_chat_id=group.wa_group_id).first()
        if not chat:
            return Response({'detail': 'No chat found for this group — messages must exist first'}, status=status.HTTP_404_NOT_FOUND)
        val = request.data.get('ai_parsing', 'inherit')
        if val in (True, 'true', '1', 1):
            chat.ai_parsing = True
        elif val in (False, 'false', '0', 0):
            chat.ai_parsing = False
        else:
            chat.ai_parsing = None
        chat.save(update_fields=['ai_parsing'])
        return Response(GroupSerializer(group).data)


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _serialize_auth_user(user):
    current_company = default_company_for_user(user)
    visible_companies = available_companies_queryset(user)
    memberships = {
        membership.company_id: membership
        for membership in user.company_memberships.filter(
            is_active=True,
            company__is_active=True,
        ).select_related('company')
    }


def _serialize_auth_user(user):
    current_company = default_company_for_user(user)
    visible_companies = available_companies_queryset(user)
    memberships = {
        membership.company_id: membership
        for membership in user.company_memberships.filter(
            is_active=True,
            company__is_active=True,
        ).select_related('company')
    }
    company_payload = None
    if current_company:
        current_membership = memberships.get(current_company.pk)
        company_payload = {
            'id': current_company.pk,
            'name': current_company.name,
            'slug': current_company.slug,
            'company_type': current_company.company_type,
            'industry_type': current_company.industry_type,
            'role': current_membership.role if current_membership else ('super_user' if user.is_superuser else ''),
        }

    return {
        'id': user.pk,
        'username': user.username,
        'email': user.email,
        'is_superuser': user.is_superuser,
        'current_company': company_payload,
        'memberships': [
            {
                'company': {
                    'id': company.pk,
                    'name': company.name,
                    'slug': company.slug,
                    'company_type': company.company_type,
                    'industry_type': company.industry_type,
                },
                'role': memberships[company.pk].role if company.pk in memberships else ('super_user' if user.is_superuser else ''),
            }
            for company in visible_companies
        ],
    }


def _require_control_admin(request):
    if is_control_company_admin(request.user):
        return None
    return Response({'detail': 'Control company admin access required'}, status=status.HTTP_403_FORBIDDEN)


def _serialize_company(company):
    membership_count = company.memberships.filter(is_active=True).count()
    return {
        'id': company.pk,
        'name': company.name,
        'slug': company.slug,
        'company_type': company.company_type,
        'industry_type': company.industry_type,
        'is_active': company.is_active,
        'valid_from': company.valid_from.isoformat() if company.valid_from else None,
        'valid_until': company.valid_until.isoformat() if company.valid_until else None,
        'notes': company.notes,
        'membership_count': membership_count,
        'created_at': company.created_at.isoformat() if company.created_at else None,
    }


def _serialize_membership(membership):
    return {
        'id': membership.pk,
        'role': membership.role,
        'is_active': membership.is_active,
        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
        'company': {
            'id': membership.company.pk,
            'name': membership.company.name,
            'slug': membership.company.slug,
        },
        'user': {
            'id': membership.user.pk,
            'username': membership.user.username,
            'email': membership.user.email,
        },
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login_view(request):
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    auth_login(request, user)
    current_company = default_company_for_user(user)
    request.session[ACTIVE_COMPANY_SESSION_KEY] = current_company.pk if current_company else None
    return Response(_serialize_auth_user(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout_view(request):
    request.session.pop(ACTIVE_COMPANY_SESSION_KEY, None)
    auth_logout(request)
    return Response({'detail': 'Logged out'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_me_view(request):
    u = request.user
    return Response(_serialize_auth_user(u))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_select_company_view(request):
    company_id = request.data.get('company_id')
    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return Response({'detail': 'company_id must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

    if not can_user_access_company(request.user, company_id):
        return Response({'detail': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)

    request.session[ACTIVE_COMPANY_SESSION_KEY] = company_id
    request.user.active_company = available_companies_queryset(request.user).filter(pk=company_id).first()
    return Response(_serialize_auth_user(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_companies_view(request):
    denied = _require_control_admin(request)
    if denied:
        return denied

    companies = Company.objects.all().order_by('name')
    return Response([_serialize_company(company) for company in companies])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_company_enroll_view(request):
    denied = _require_control_admin(request)
    if denied:
        return denied

    company_name = (request.data.get('company_name') or '').strip()
    email = (request.data.get('email') or '').strip()
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''
    industry_type = (request.data.get('industry_type') or Company.INDUSTRY_GENERAL).strip()

    try:
        result = CompanyEnrollmentService().enroll_company(
            company_name=company_name,
            email=email,
            username=username,
            password=password,
            industry_type=industry_type,
        )
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    company = Company.objects.get(pk=result.company_id)
    membership = CompanyMembership.objects.select_related('company', 'user').get(pk=result.membership_id)
    return Response(
        {
            'company': _serialize_company(company),
            'membership': _serialize_membership(membership),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def admin_company_users_view(request):
    denied = _require_control_admin(request)
    if denied:
        return denied

    if request.method == 'GET':
        company_id = request.query_params.get('company_id')
        memberships = CompanyMembership.objects.select_related('company', 'user').filter(is_active=True)
        if company_id:
            memberships = memberships.filter(company_id=company_id)
        memberships = memberships.order_by('company__name', 'user__username')
        return Response([_serialize_membership(membership) for membership in memberships])

    company_id = request.data.get('company_id')
    email = (request.data.get('email') or '').strip()
    username = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''
    role = (request.data.get('role') or CompanyMembership.ROLE_USER).strip()

    try:
        company = Company.objects.get(pk=company_id, is_active=True)
    except Company.DoesNotExist:
        return Response({'detail': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        result = CompanyEnrollmentService().create_company_user(
            company=company,
            email=email,
            username=username,
            password=password,
            role=role,
        )
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    membership = CompanyMembership.objects.select_related('company', 'user').get(pk=result.membership_id)
    return Response(_serialize_membership(membership), status=status.HTTP_201_CREATED)
