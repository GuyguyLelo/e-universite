from django.urls import path
from .views import *

app_name = 'evaluations'

urlpatterns = [
    # Types d'évaluation
    path('types-evaluation/', type_evaluation_list, name='type_evaluation_list'),
    path('types-evaluation/nouveau/', type_evaluation_create, name='type_evaluation_create'),
    path('types-evaluation/<int:pk>/modifier/', type_evaluation_update, name='type_evaluation_update'),
    path('types-evaluation/<int:pk>/supprimer/', type_evaluation_delete, name='type_evaluation_delete'),
    
    # Sessions
    path('sessions/', session_list, name='session_list'),
    path('sessions/nouvelle/', session_create, name='session_create'),
    path('sessions/<int:pk>/modifier/', session_update, name='session_update'),
    path('sessions/<int:pk>/supprimer/', session_delete, name='session_delete'),
    path('sessions/<int:pk>/verrouiller/', session_verrouiller, name='session_verrouiller'),
    path('sessions/<int:pk>/deverrouiller/', session_deverrouiller, name='session_deverrouiller'),
    path('sessions/<int:pk>/rattrapage/', session_prepare_rattrapage, name='session_prepare_rattrapage'),
    
    # Évaluations
    path('evaluations/', evaluation_list, name='evaluation_list'),
    path('evaluations/nouvelle/', evaluation_create, name='evaluation_create'),
    path('evaluations/<int:pk>/modifier/', evaluation_update, name='evaluation_update'),
    path('evaluations/<int:pk>/supprimer/', evaluation_delete, name='evaluation_delete'),
    path('api/ecs-evaluation/', api_ecs_evaluation, name='api_ecs_evaluation'),
    path('evaluations/<int:evaluation_id>/saisie-masse/', saisie_masse_notes, name='saisie_masse_notes'),
    
    # Notes
    path('notes/', note_list, name='note_list'),
    path('notes/fiche-cotation/pdf/', fiche_cotation_pdf, name='fiche_cotation_pdf'),
    path('notes/export-excel/', note_export_excel, name='note_export_excel'),
    path('notes/import-excel/', note_import_excel, name='note_import_excel'),
    path('notes/consultation/', note_consultation, name='note_consultation'),
    path('notes/nouvelle/', note_create, name='note_create'),
    path('notes/<int:pk>/modifier/', note_update, name='note_update'),
    path('notes/<int:pk>/supprimer/', note_delete, name='note_delete'),
    path('notes/par-etudiant/', note_par_etudiant, name='note_par_etudiant'),
    path('notes/par-ec/', note_par_ec, name='note_par_ec'),
]
