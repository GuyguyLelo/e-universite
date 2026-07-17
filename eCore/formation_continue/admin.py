from django.contrib import admin

from .models import (
    Brevet,
    Formateur,
    Inscription,
    ModuleTIC,
    OffreModule,
    Presence,
    Seminariste,
    SessionFormation,
)


@admin.register(SessionFormation)
class SessionFormationAdmin(admin.ModelAdmin):
    list_display = (
        'libelle', 'annee', 'numero', 'date_debut', 'date_fin',
        'active', 'cloturee', 'date_cloture',
    )
    list_filter = ('annee', 'active', 'cloturee')
    search_fields = ('libelle',)
    readonly_fields = ('date_cloture', 'cloturee_par')


@admin.register(ModuleTIC)
class ModuleTICAdmin(admin.ModelAdmin):
    list_display = ('code', 'intitule', 'duree_heures', 'active')
    search_fields = ('code', 'intitule')
    list_filter = ('active',)


@admin.register(Formateur)
class FormateurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'specialite', 'telephone', 'email', 'active')
    search_fields = ('nom', 'prenom', 'email')
    list_filter = ('active',)


@admin.register(Seminariste)
class SeminaristeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'type_participant', 'organisation', 'telephone', 'active')
    list_filter = ('type_participant', 'active')
    search_fields = ('nom', 'prenom', 'matricule', 'organisation')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OffreModule)
class OffreModuleAdmin(admin.ModelAdmin):
    list_display = ('session', 'module', 'formateur', 'date_debut', 'date_fin')
    list_filter = ('session',)
    search_fields = ('module__code', 'module__intitule', 'formateur__nom', 'formateur__prenom')
    autocomplete_fields = ('session', 'module', 'formateur')


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ('seminariste', 'session', 'date_inscription', 'statut')
    list_filter = ('session', 'statut')
    search_fields = ('seminariste__nom', 'seminariste__prenom', 'session__libelle')
    filter_horizontal = ('modules',)
    autocomplete_fields = ('seminariste', 'session')


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ('inscription', 'offre_module', 'date_seance', 'statut')
    list_filter = ('statut', 'date_seance')
    autocomplete_fields = ('inscription', 'offre_module')


@admin.register(Brevet)
class BrevetAdmin(admin.ModelAdmin):
    list_display = ('numero', 'seminariste', 'session', 'date_delivrance')
    list_filter = ('session',)
    search_fields = ('numero', 'seminariste__nom', 'seminariste__prenom')
    filter_horizontal = ('modules_valides',)
    autocomplete_fields = ('seminariste', 'session')
