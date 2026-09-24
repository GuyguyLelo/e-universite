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
    path('paiements/', views.paiement_list, name='paiement_list'),
    path('paiements/nouveau/', views.paiement_create, name='paiement_create'),
    path('paiements/<int:pk>/recu.pdf', views.paiement_recu_pdf, name='paiement_recu'),
    path('paiements/<int:pk>/', views.paiement_detail, name='paiement_detail'),
    path('paiements/<int:pk>/modifier/', views.paiement_update, name='paiement_update'),
    path('paiements/<int:pk>/supprimer/', views.paiement_delete, name='paiement_delete'),
    path('recu/<str:reference>/', views.recu_public, name='recu_public'),
    path(
        'api/etudiant-en-ordre/toggle/',
        views.api_etudiant_en_ordre_toggle,
        name='api_etudiant_en_ordre_toggle',
    ),
]
