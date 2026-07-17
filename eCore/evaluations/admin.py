from django.contrib import admin
from .models import TypeEvaluation, Session, Evaluation, Note, NoteEC, NoteUE


@admin.register(TypeEvaluation)
class TypeEvaluationAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'coefficient', 'note_max', 'ordre', 'active']
    list_filter = ['active']
    search_fields = ['code', 'nom']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'annee_academique', 'semestre', 'numero', 'date_debut', 'date_fin', 'deliberation_faite', 'verrouillee']
    list_filter = ['annee_academique', 'deliberation_faite', 'verrouillee', 'semestre']
    search_fields = ['code', 'nom']


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'annee_academique', 'ec', 'session', 'type_evaluation', 'date_evaluation', 'coefficient', 'active']
    list_filter = ['annee_academique', 'session', 'type_evaluation', 'active']
    search_fields = ['code', 'nom']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'evaluation', 'note', 'absent', 'justifie', 'date_saisie']
    list_filter = ['absent', 'justifie', 'evaluation__session']
    search_fields = ['etudiant__numero_etudiant', 'etudiant__nom', 'evaluation__code']


@admin.register(NoteEC)
class NoteECAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'ec', 'session', 'note_finale', 'credits_obtenus', 'valide', 'capitalise']
    list_filter = ['session', 'valide', 'capitalise', 'calculee_auto']
    search_fields = ['etudiant__numero_etudiant', 'ec__code']


@admin.register(NoteUE)
class NoteUEAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'ue', 'session', 'note_finale', 'credits_obtenus', 'valide', 'capitalise']
    list_filter = ['session', 'valide', 'capitalise', 'calculee_auto']
    search_fields = ['etudiant__numero_etudiant', 'ue__code']
