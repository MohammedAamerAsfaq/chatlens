import logging
import threading
from django.db import connection as _db_conn
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.tenancy.services.access import visible_accounts_queryset

logger = logging.getLogger(__name__)


def _visible_account_id(request, raw_account_id):
    try:
        account_id = int(raw_account_id)
    except (TypeError, ValueError):
        return None
    return (
        visible_accounts_queryset(request.user)
        .filter(pk=account_id)
        .values_list('pk', flat=True)
        .first()
    )


def _visible_messages(request, queryset, raw_account_id=None):
    if raw_account_id not in (None, ''):
        account_id = _visible_account_id(request, raw_account_id)
        if account_id is None:
            return None
        return queryset.filter(account_id=account_id)
    visible_account_ids = visible_accounts_queryset(request.user).values('pk')
    return queryset.filter(account_id__in=visible_account_ids)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def semantic_search_view(request):
    """POST { query, account_id, top_k? } → ranked message list."""
    query = (request.data.get('query') or '').strip()
    account_id = request.data.get('account_id')
    top_k = int(request.data.get('top_k', 10))

    if not query:
        return Response({'error': 'query is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not account_id:
        return Response({'error': 'account_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    visible_account_id = _visible_account_id(request, account_id)
    if visible_account_id is None:
        return Response({'detail': 'Account not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        from .services.embedding_service import semantic_search
        hits = semantic_search(query, account_id=visible_account_id, top_k=top_k)
    except Exception as exc:
        logger.exception('semantic_search_view error')
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    results = []
    for hit in hits:
        msg = hit.message
        results.append({
            'message_id': msg.pk,
            'score': round(1 - float(hit.distance), 4),
            'message_text': msg.message_text,
            'message_time': msg.message_time.isoformat(),
            'direction': msg.direction,
            'chat_id': msg.chat_id,
            'contact_id': msg.contact_id,
        })

    return Response({'query': query, 'results': results, 'total': len(results)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def embedding_status_view(request):
    """GET /api/intelligence/embedding-status/?account_id=X
    Returns counts of messages with/without embeddings for an account (or all accounts).
    """
    from apps.whatsapp_bridge.models import WhatsAppMessage

    account_id = request.query_params.get('account_id')
    qs = _visible_messages(
        request,
        WhatsAppMessage.objects.filter(message_text__gt=''),
        account_id,
    )
    if qs is None:
        return Response({'detail': 'Account not found.'}, status=status.HTTP_404_NOT_FOUND)

    total    = qs.count()
    embedded = qs.filter(embedding__isnull=False).count()
    pending  = total - embedded

    return Response({'total': total, 'embedded': embedded, 'pending': pending})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def embedding_backfill_view(request):
    """POST /api/intelligence/backfill/  body: { account_id?, limit? }
    Starts a background thread to embed pending messages and returns immediately.
    """
    from apps.whatsapp_bridge.models import WhatsAppMessage

    account_id = request.data.get('account_id')
    limit      = int(request.data.get('limit', 500))

    qs = _visible_messages(request, (
        WhatsAppMessage.objects
        .filter(message_text__gt='')
        .filter(Q(embedding__isnull=True))
        .order_by('id')
    ), account_id)
    if qs is None:
        return Response({'detail': 'Account not found.'}, status=status.HTTP_404_NOT_FOUND)

    pending = qs.count()
    if pending == 0:
        return Response({'started': False, 'pending': 0, 'message': 'Nothing to embed'})

    ids = list(qs.values_list('id', flat=True)[:limit])

    def _run():
        try:
            from apps.message_intelligence.services.embedding_service import embed_messages_batch
            result = embed_messages_batch(ids)
            logger.info(
                'Admin backfill complete — account=%s embedded=%s errors=%s',
                account_id or 'all', result['embedded'], result['errors'],
            )
        except Exception:
            logger.exception('Admin backfill failed — account=%s', account_id or 'all')
        finally:
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()

    return Response({
        'started': True,
        'pending': pending,
        'processing': len(ids),
        'message': f'Embedding {len(ids)} messages in background ({"all" if pending <= limit else f"{limit} of {pending}"} pending)',
    })
