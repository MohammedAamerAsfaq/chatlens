import requests
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppChat, SyncLog
from .serializers import (
    WhatsAppAccountSerializer, ChatSerializer, MessageSerializer, SyncLogSerializer,
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

    @action(detail=True, methods=['post'], url_path='start-session')
    def start_session(self, request, pk=None):
        account = self.get_object()
        try:
            resp = requests.post(
                f'{WORKER_BASE_URL}/sessions',
                json={'session_id': str(account.pk)},
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

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        chat = self.get_object()
        chat.unread_count = 0
        chat.save(update_fields=['unread_count'])
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


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncLogSerializer
    permission_classes = [AllowAny]

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
        return qs[:200]
