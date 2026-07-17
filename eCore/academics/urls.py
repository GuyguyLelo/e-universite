from django.urls import path
from .views import *

app_name = 'academics'

urlpatterns = [
    # Sections
    path('sections/', section_list, name='section_list'),
    path('sections/nouvelle/', section_create, name='section_create'),
    path('sections/<int:pk>/modifier/', section_update, name='section_update'),
    path('sections/<int:pk>/supprimer/', section_delete, name='section_delete'),
    
    # Filières
    path('filieres/', filiere_list, name='filiere_list'),
    path('filieres/nouveau/', filiere_create, name='filiere_create'),
    path('filieres/<int:pk>/modifier/', filiere_update, name='filiere_update'),
    path('filieres/<int:pk>/supprimer/', filiere_delete, name='filiere_delete'),
    
    # Années académiques
    path('annees-academiques/', annee_academique_list, name='annee_academique_list'),
    path('annees-academiques/nouvelle/', annee_academique_create, name='annee_academique_create'),
    path('annees-academiques/<int:pk>/modifier/', annee_academique_update, name='annee_academique_update'),
    path('annees-academiques/<int:pk>/supprimer/', annee_academique_delete, name='annee_academique_delete'),
    
    # Promotions
    path('promotions/', promotion_list, name='promotion_list'),
    path('promotions/nouvelle/', promotion_create, name='promotion_create'),
    path('promotions/<int:pk>/', promotion_detail, name='promotion_detail'),
    path('promotions/<int:pk>/modifier/', promotion_update, name='promotion_update'),
    path('promotions/<int:pk>/supprimer/', promotion_delete, name='promotion_delete'),

    # Locaux
    path('locaux/', local_list, name='local_list'),
    path('locaux/nouveau/', local_create, name='local_create'),
    path('locaux/<int:pk>/modifier/', local_update, name='local_update'),
    path('locaux/<int:pk>/supprimer/', local_delete, name='local_delete'),

    # Classes
    path('classes/', classe_list, name='classe_list'),
    path('classes/nouvelle/', classe_create, name='classe_create'),
    path('classes/<int:pk>/modifier/', classe_update, name='classe_update'),
    path('classes/<int:pk>/supprimer/', classe_delete, name='classe_delete'),

    # API (dropdowns dépendants)
    path('api/filieres/', api_filieres, name='api_filieres'),
    path('api/promotions/', api_promotions, name='api_promotions'),
    path('api/classes/', api_classes, name='api_classes'),
    path('api/local/', api_local, name='api_local'),
    
    # Semestres
    path('semestres/', semestre_list, name='semestre_list'),
    path('semestres/nouveau/', semestre_create, name='semestre_create'),
    path('semestres/<int:pk>/modifier/', semestre_update, name='semestre_update'),
    path('semestres/<int:pk>/supprimer/', semestre_delete, name='semestre_delete'),
    
    # Unités d'Enseignement
    path('ues/', ue_list, name='ue_list'),
    path('ues/nouvelle/', ue_create, name='ue_create'),
    path('ues/<int:pk>/modifier/', ue_update, name='ue_update'),
    path('ues/<int:pk>/supprimer/', ue_delete, name='ue_delete'),
    
    # Éléments Constitutifs
    path('ecs/', ec_list, name='ec_list'),
    path('ecs/nouveau/', ec_create, name='ec_create'),
    path('ecs/<int:pk>/modifier/', ec_update, name='ec_update'),
    path('ecs/<int:pk>/supprimer/', ec_delete, name='ec_delete'),
]
