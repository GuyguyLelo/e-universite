from django.contrib import admin
from .models import TypeDocumentGenere, DocumentGenere, TypeAttestation, Attestation


@admin.register(TypeDocumentGenere)
class TypeDocumentGenereAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'active']
    list_filter = ['active']
    search_fields = ['code', 'nom']


@admin.register(DocumentGenere)
class DocumentGenereAdmin(admin.ModelAdmin):
    list_display = ['type_document', 'etudiant', 'session', 'date_generation', 'genere_par']
    list_filter = ['type_document', 'date_generation', 'session']
    search_fields = ['etudiant__numero_etudiant', 'etudiant__nom', 'etudiant__prenom']
    readonly_fields = ['date_generation', 'created_at', 'updated_at']


@admin.register(TypeAttestation)
class TypeAttestationAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'ordre', 'active']
    list_filter = ['active']
    search_fields = ['code', 'nom']


@admin.register(Attestation)
class AttestationAdmin(admin.ModelAdmin):
    list_display = ['numero', 'type_attestation', 'inscription', 'date_delivrance', 'date_generation']
    list_filter = ['type_attestation', 'date_delivrance']
    search_fields = ['numero', 'inscription__etudiant__numero_etudiant', 'inscription__etudiant__nom']
    readonly_fields = ['numero', 'date_generation', 'genere_par', 'created_at', 'updated_at']
