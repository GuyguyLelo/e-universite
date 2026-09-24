from django.urls import path
from .views import *

app_name = 'students'

urlpatterns = [
    # Étudiants
    path('mon-espace/', mon_espace, name='mon_espace'),
    path('mon-espace/payer/', mon_espace_payer, name='mon_espace_payer'),
    path('mon-espace/paiements/<int:pk>/recu.pdf', mon_espace_recu_pdf, name='mon_espace_recu'),
    path('etudiants/', student_list, name='student_list'),
    path('etudiants/nouveau/', student_create, name='student_create'),
    path('etudiants/importer/', student_import, name='student_import'),
    path('etudiants/<int:pk>/', student_detail, name='student_detail'),
    path('etudiants/<int:pk>/fiche-scolarite/', student_fiche_scolarite, name='student_fiche_scolarite'),
    path('etudiants/<int:pk>/carte.pdf', student_carte_pdf, name='student_carte_pdf'),
    path('etudiants/<int:pk>/qrcode/', student_qrcode, name='student_qrcode'),
    path('carte/<uuid:code_unique>/', student_card_public, name='student_card_public'),
    path('etudiants/<int:pk>/modifier/', student_update, name='student_update'),
    path('etudiants/<int:pk>/supprimer/', student_delete, name='student_delete'),
    
    # Inscriptions
    path('inscriptions/', inscription_list, name='inscription_list'),
    path('inscriptions/nouvelle/', inscription_create, name='inscription_create'),
    path('inscriptions/<int:pk>/', inscription_detail, name='inscription_detail'),
    path('inscriptions/<int:pk>/abandon/', inscription_abandon, name='inscription_abandon'),
    path('inscriptions/<int:pk>/reintegrer/', inscription_reintegrer, name='inscription_reintegrer'),
    path('inscriptions/<int:pk>/modifier/', inscription_update, name='inscription_update'),
    path('inscriptions/<int:pk>/supprimer/', inscription_delete, name='inscription_delete'),
    
    # Documents (dépôt via checklist dossier ; liste / modification / suppression)
    path('documents/', document_list, name='document_list'),
    path('documents/<int:pk>/modifier/', document_update, name='document_update'),
    path('documents/<int:pk>/supprimer/', document_delete, name='document_delete'),
    
    # Types de documents
    path('types-documents/', type_document_list, name='type_document_list'),
    path('types-documents/nouveau/', type_document_create, name='type_document_create'),
    path('types-documents/<int:pk>/modifier/', type_document_update, name='type_document_update'),
    path('types-documents/<int:pk>/supprimer/', type_document_delete, name='type_document_delete'),
    
    # Dossiers
    path('dossiers/', dossier_list, name='dossier_list'),
    path('dossiers/<int:pk>/', dossier_detail, name='dossier_detail'),
    path('dossiers/<int:pk>/toggle-document/', dossier_toggle_document, name='dossier_toggle_document'),
]
