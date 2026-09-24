from django.contrib import admin
from .models import (
    Section, Faculte, Departement, Filiere, Promotion, Classe, Local,
    AnneeAcademique, Semestre,
    UniteEnseignement, ElementConstitutif
)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['code', 'nom']


@admin.register(Faculte)
class FaculteAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'etablissement', 'active']
    list_filter = ['etablissement', 'active']
    search_fields = ['code', 'nom']


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'faculte', 'active']
    list_filter = ['faculte', 'active']
    search_fields = ['code', 'nom']


@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'departement', 'faculte', 'section', 'active']
    list_filter = ['faculte', 'departement', 'section', 'active']
    search_fields = ['code', 'nom']


@admin.register(AnneeAcademique)
class AnneeAcademiqueAdmin(admin.ModelAdmin):
    list_display = ['code', 'annee_debut', 'annee_fin', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['code']


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'filiere', 'ordre', 'active', 'created_at']
    list_filter = ['filiere', 'active', 'created_at']
    search_fields = ['code', 'nom']

@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'capacite', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['code', 'nom']


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ['code', 'promotion', 'local', 'effectif_max', 'active', 'created_at']
    list_filter = ['promotion', 'local', 'active', 'created_at']
    search_fields = ['code', 'nom']


@admin.register(Semestre)
class SemestreAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'numero', 'credits_ects', 'active', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['code', 'nom']


@admin.register(UniteEnseignement)
class UniteEnseignementAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'semestre', 'filiere', 'credits_ects', 'coefficient', 'seuil_validation', 'active']
    list_filter = ['semestre', 'filiere', 'active', 'compensation_autorisee', 'capitalisable']
    search_fields = ['code', 'nom']


@admin.register(ElementConstitutif)
class ElementConstitutifAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'ue', 'professeur', 'credits_ects', 'coefficient', 'seuil_validation', 'note_eliminatoire', 'active']
    list_filter = ['ue', 'active', 'compensation_autorisee', 'capitalisable']
    search_fields = ['code', 'nom']
