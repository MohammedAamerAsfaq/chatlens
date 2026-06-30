from django.urls import path
from . import views

urlpatterns = [
    path('intelligence/search/', views.semantic_search_view, name='semantic-search'),
]
