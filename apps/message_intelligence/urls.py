from django.urls import path
from . import views

urlpatterns = [
    path('intelligence/search/',            views.semantic_search_view,     name='semantic-search'),
    path('intelligence/embedding-status/',  views.embedding_status_view,    name='embedding-status'),
    path('intelligence/backfill/',          views.embedding_backfill_view,  name='embedding-backfill'),
]
