from django.contrib import admin

from .models import ProjetAcademique


@admin.register(ProjetAcademique)
class ProjetAcademiqueAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'annee_academique', 'filiere', 'semestre', 'tuteur',
        'date_finalisation', 'statut',
    ]
    list_filter = ['statut', 'annee_academique', 'filiere', 'semestre']
    search_fields = ['titre', 'resume', 'mots_cles', 'tuteur', 'etudiants__nom', 'etudiants__prenom']
    filter_horizontal = ['etudiants']
    date_hierarchy = 'date_finalisation'
    readonly_fields = ['created_at', 'updated_at']
