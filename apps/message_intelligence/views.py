import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


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

    try:
        from .services.embedding_service import semantic_search
        hits = semantic_search(query, account_id=account_id, top_k=top_k)
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
