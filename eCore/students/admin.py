from django.contrib import admin
from .models import Student, Inscription, TypeDocument, DocumentEtudiant, DossierEtudiant


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['numero_etudiant', 'nom', 'prenom', 'email', 'statut', 'date_inscription']
    list_filter = ['statut', 'sexe', 'nationalite', 'date_inscription']
    search_fields = ['numero_etudiant', 'nom', 'prenom', 'email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ['numero_inscription', 'etudiant', 'classe', 'annee_academique', 'statut', 'date_abandon', 'dossier_complet', 'date_inscription']
    list_filter = ['statut', 'dossier_complet', 'classe', 'annee_academique', 'date_inscription', 'date_abandon']
    search_fields = ['numero_inscription', 'etudiant__numero_etudiant', 'etudiant__nom', 'etudiant__prenom']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TypeDocument)
class TypeDocumentAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'obligatoire', 'ordre', 'active']
    list_filter = ['obligatoire', 'active']
    search_fields = ['code', 'nom']


@admin.register(DocumentEtudiant)
class DocumentEtudiantAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'type_document', 'date_depot', 'valide', 'date_validation']
    list_filter = ['valide', 'type_document', 'date_depot']
    search_fields = ['etudiant__numero_etudiant', 'etudiant__nom', 'etudiant__prenom']


@admin.register(DossierEtudiant)
class DossierEtudiantAdmin(admin.ModelAdmin):
    list_display = ['inscription', 'statut', 'date_ouverture', 'date_fermeture']
    list_filter = ['statut', 'date_ouverture']
    search_fields = ['inscription__etudiant__numero_etudiant']
