from django.contrib import admin

from .models import ConfirmationPaiement, MotifPaiement, Paiement


@admin.register(MotifPaiement)
class MotifPaiementAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'nom',
        'annee_academique',
        'semestre',
        'contexte',
        'montant',
        'devise',
        'ordre',
        'active',
    )
    list_filter = ('active', 'annee_academique', 'semestre', 'contexte', 'devise')
    search_fields = ('code', 'nom', 'annee_academique__code')
    ordering = (
        '-annee_academique__annee_debut',
        'semestre__numero',
        'contexte',
        'ordre',
        'nom',
    )


@admin.register(ConfirmationPaiement)
class ConfirmationPaiementAdmin(admin.ModelAdmin):
    list_display = ('inscription', 'motif_paiement', 'confirme', 'date_confirmation', 'confirme_par')
    list_filter = ('confirme', 'motif_paiement__annee_academique', 'motif_paiement__contexte')
    search_fields = (
        'inscription__etudiant__numero_etudiant',
        'inscription__etudiant__nom',
        'motif_paiement__code',
    )


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'inscription',
        'motif_paiement',
        'montant',
        'devise',
        'mode',
        'statut',
        'date_paiement',
    )
    list_filter = ('statut', 'mode', 'devise', 'operateur')
    search_fields = (
        'reference',
        'reference_transaction',
        'inscription__etudiant__numero_etudiant',
        'inscription__etudiant__nom',
        'telephone',
    )
    readonly_fields = ('reference', 'created_at', 'updated_at')
