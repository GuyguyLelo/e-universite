from django.contrib import admin
from .models import ParametresLMD, Deliberation, DecisionJury


@admin.register(ParametresLMD)
class ParametresLMDAdmin(admin.ModelAdmin):
    list_display = ['promotion', 'seuil_validation', 'compensation_intra_ue', 'compensation_intra_semestre', 'compensation_annuelle']
    list_filter = ['compensation_intra_ue', 'compensation_intra_semestre', 'compensation_annuelle']


@admin.register(Deliberation)
class DeliberationAdmin(admin.ModelAdmin):
    list_display = ['type_deliberation', 'libelle_court', 'promotion', 'date_deliberation', 'statut', 'president_jury']
    list_filter = ['type_deliberation', 'statut', 'date_deliberation']
    filter_horizontal = ['membres_jury']


@admin.register(DecisionJury)
class DecisionJuryAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'deliberation', 'decision', 'moyenne_semestre', 'credits_obtenus', 'rang', 'mention']
    list_filter = ['decision', 'deliberation', 'mention']
    search_fields = ['etudiant__numero_etudiant', 'etudiant__nom']
