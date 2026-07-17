from django.urls import path
from .views import accueil, dashboard, home, projets_tutores_realises

urlpatterns = [
    path('', home, name='home'),
    path('accueil/', accueil, name='accueil'),
    path('dashboard/', dashboard, name='dashboard'),
    path('projets-tutores-realises/', projets_tutores_realises, name='projets_tutores_realises'),
]
