from django.urls import path
from .views import *

app_name = 'documents'

urlpatterns = [
    path('releve-notes/', releve_notes_selection, name='releve_notes_selection'),
    path('releve-notes/export/', releve_notes_export_bulk, name='releve_notes_export_bulk'),
    path('releve-notes/<int:etudiant_id>/<int:session_id>/', generate_releve_notes, name='generate_releve_notes'),
    path('proces-verbal/<int:deliberation_id>/', generate_proces_verbal, name='generate_proces_verbal'),
    path('attestation/<int:inscription_id>/<str:type_attestation>/', generate_attestation, name='generate_attestation'),
    path('grille/', grille_notes, name='grille_notes'),
    path('attestations/', attestation_list, name='attestation_list'),
    path('attestations/nouvelle/', attestation_create, name='attestation_create'),
    path('attestations/<int:pk>/modifier/', attestation_update, name='attestation_update'),
    path('attestations/<int:pk>/supprimer/', attestation_delete, name='attestation_delete'),
    path('attestations/<int:pk>/pdf/', attestation_pdf, name='attestation_pdf'),
]
