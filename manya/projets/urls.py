from django.urls import path

from . import views

app_name = 'projets'

urlpatterns = [
    path('', views.projets_accueil, name='accueil'),
    path('consultation/', views.projet_consultation_list, name='projet_consultation_list'),
    path('consultation/<int:pk>/', views.projet_consultation_detail, name='projet_consultation_detail'),
    path('gestion/', views.projet_list, name='projet_list'),
    path('gestion/nouveau/', views.projet_create, name='projet_create'),
    path('gestion/<int:pk>/', views.projet_detail, name='projet_detail'),
    path('gestion/<int:pk>/modifier/', views.projet_update, name='projet_update'),
    path('gestion/<int:pk>/supprimer/', views.projet_delete, name='projet_delete'),
]
