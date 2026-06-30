import io
import json
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
from django.db.models import Count, Q
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.whatsapp_bridge.models import (
    WhatsAppAccount, WhatsAppChat, WhatsAppMessage, WhatsAppContact,
    SyncLog, DroppedMessage, WhatsAppGroup,
)
from .serializers import (
    WhatsAppAccountSerializer, ChatSerializer, MessageSerializer,
    SyncLogSerializer, DroppedMessageSerializer, ContactDetailSerializer,
    GroupSerializer, GroupDetailSerializer,
)

WORKER_BASE_URL = getattr(settings, 'WORKER_BASE_URL', 'http://localhost:3001')


class WhatsAppAccountViewSet(viewsets.ModelViewSet):
    queryset = WhatsAppAccount.objects.all().order_by('-created_at')
    serializer_class = WhatsAppAccountSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            owner = self.request.user
        else:
            owner = User.objects.filter(is_superuser=True).first()
        serializer.save(owner=owner)

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
        allowed = ['sync_history', 'history_days', 'idle_disconnect_minutes', 'display_name']
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
        WhatsAppAccount.objects.update(auto_download_media=enabled)
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
        deleted, _ = WhatsAppMessage.objects.all().delete()
        WhatsAppChat.objects.update(unread_count=0, last_message_at=None)
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
        media_root = Path(settings.WORKER_MEDIA_PATH)
        removed_bytes = 0
        removed_files = 0
        if media_root.exists():
            for f in media_root.rglob('*'):
                if f.is_file():
                    removed_bytes += f.stat().st_size
                    removed_files += 1
            shutil.rmtree(media_root)
            media_root.mkdir(parents=True, exist_ok=True)
        WhatsAppMessage.objects.filter(has_media=True).update(media_url='')
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

            to_create = []
            for msg in chat_data.get('messages', []):
                pid = msg.get('provider_message_id')
                if not pid:
                    continue
                mt = parse_datetime(str(msg['message_time'])) if msg.get('message_time') else None
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
                created_objs = WhatsAppMessage.objects.bulk_create(
                    to_create, ignore_conflicts=True,
                )
                restored_messages += len(created_objs)

            # Refresh chat timestamps
            latest = chat.messages.order_by('-message_time').first()
            if latest:
                chat.last_message_at = latest.message_time
                chat.save(update_fields=['last_message_at'])

        return Response({'restored_chats': restored_chats, 'restored_messages': restored_messages})

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
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class ChatViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = WhatsAppChat.objects.select_related('contact').order_by('-last_message_at')
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(contact__display_name__icontains=search) | \
                 qs.filter(contact__phone_number__icontains=search) | \
                 qs.filter(wa_chat_id__icontains=search)
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

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        chat = self.get_object()
        chat.unread_count = 0
        chat.save(update_fields=['unread_count'])
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        account_id = request.query_params.get('account')
        qs = WhatsAppChat.objects.all()
        if account_id:
            qs = qs.filter(account_id=account_id)
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
    permission_classes = [AllowAny]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = SyncLog.objects.select_related('account').order_by('-created_at')
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)
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
        qs = SyncLog.objects.all()
        account_id = request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)
        deleted, _ = qs.delete()
        return Response({'deleted': deleted})


class DroppedMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DroppedMessageSerializer
    permission_classes = [AllowAny]
    pagination_class = ActivityPagination

    def get_queryset(self):
        qs = DroppedMessage.objects.select_related('account').order_by('-created_at')
        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)
        reason = self.request.query_params.get('reason')
        if reason:
            qs = qs.filter(reason=reason)
        return qs

    @action(detail=False, methods=['post'], url_path='clear-all')
    def clear_all(self, request):
        qs = DroppedMessage.objects.all()
        account_id = request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)
        deleted, _ = qs.delete()
        return Response({'deleted': deleted})


class ContactViewSet(viewsets.ModelViewSet):
    serializer_class = ContactDetailSerializer
    permission_classes = [AllowAny]
    pagination_class = ActivityPagination
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = (
            WhatsAppContact.objects
            .select_related('account')
            .prefetch_related('chats')
            .annotate(message_count=Count('messages', distinct=True))
            .order_by('display_name', 'push_name', 'phone_number')
        )

        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)

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

        return qs

    def partial_update(self, request, *args, **kwargs):
        contact = self.get_object()
        # Only display_name is user-editable; ignore any other fields in request
        data = {'display_name': request.data.get('display_name', contact.display_name)}
        serializer = self.get_serializer(contact, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        account_id = request.query_params.get('account')
        qs = WhatsAppContact.objects.all()
        if account_id:
            qs = qs.filter(account_id=account_id)
        return Response({
            'total':    qs.count(),
            'phone':    qs.filter(wa_contact_id__endswith='@s.whatsapp.net').count(),
            'lid':      qs.filter(wa_contact_id__endswith='@lid').count(),
            'group':    qs.filter(wa_contact_id__endswith='@g.us').count(),
            'username': qs.filter(username__isnull=False).exclude(username='').count(),
        })


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = ActivityPagination

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GroupDetailSerializer
        return GroupSerializer

    def get_queryset(self):
        qs = WhatsAppGroup.objects.select_related('account', 'community').order_by('-updated_at')

        account_id = self.request.query_params.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)

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
        qs = WhatsAppGroup.objects.all()
        if account_id:
            qs = qs.filter(account_id=account_id)
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
        try:
            account = WhatsAppAccount.objects.get(pk=account_id)
        except WhatsAppAccount.DoesNotExist:
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
