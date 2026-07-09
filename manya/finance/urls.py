from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('motifs-paiement/', views.motif_paiement_list, name='motif_paiement_list'),
    path('motifs-paiement/nouveau/', views.motif_paiement_create, name='motif_paiement_create'),
    path('motifs-paiement/<int:pk>/', views.motif_paiement_detail, name='motif_paiement_detail'),
    path('motifs-paiement/<int:pk>/modifier/', views.motif_paiement_update, name='motif_paiement_update'),
    path('motifs-paiement/<int:pk>/supprimer/', views.motif_paiement_delete, name='motif_paiement_delete'),
    path('etudiants-en-ordre/', views.etudiant_en_ordre_list, name='etudiant_en_ordre_list'),
    path(
        'api/etudiant-en-ordre/toggle/',
        views.api_etudiant_en_ordre_toggle,
        name='api_etudiant_en_ordre_toggle',
    ),
]
