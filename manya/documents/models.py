"""
Modèles pour la gestion des documents générés
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from students.models import Student, Inscription
from evaluations.models import Session
from deliberations.models import Deliberation
import os


def document_generated_path(instance, filename):
    """Génère le chemin pour les documents générés"""
    return f'documents/generated/{instance.type_document}/{instance.etudiant.numero_etudiant if instance.etudiant else "deliberation"}/{filename}'


def attestation_pdf_path(instance, filename):
    annee = instance.inscription.annee_academique.code if instance.inscription_id else 'sans_annee'
    matricule = instance.etudiant.numero_etudiant if instance.etudiant else 'inconnu'
    return f'documents/attestations/{annee}/{matricule}/{filename}'


class TypeDocumentGenere(models.Model):
    """Types de documents générables"""
    code = models.CharField(max_length=40, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    template_pdf = models.CharField(max_length=200, blank=True, null=True, verbose_name="Template PDF")
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Type de document généré"
        verbose_name_plural = "Types de documents générés"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class DocumentGenere(models.Model):
    """Document PDF généré"""
    type_document = models.ForeignKey(TypeDocumentGenere, on_delete=models.CASCADE, related_name='documents', verbose_name="Type de document")
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Étudiant")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Inscription")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Session")
    deliberation = models.ForeignKey(Deliberation, on_delete=models.CASCADE, related_name='documents_generes', null=True, blank=True, verbose_name="Délibération")
    fichier = models.FileField(upload_to=document_generated_path, verbose_name="Fichier PDF")
    date_generation = models.DateTimeField(auto_now_add=True, verbose_name="Date de génération")
    genere_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Généré par")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Document généré"
        verbose_name_plural = "Documents générés"
        ordering = ['-date_generation']

    def __str__(self):
        if self.etudiant:
            return f"{self.type_document.nom} - {self.etudiant.numero_etudiant}"
        return f"{self.type_document.nom} - {self.date_generation.strftime('%Y-%m-%d')}"


class TypeAttestation(models.Model):
    """Types d'attestations délivrables (scolarité, inscription, etc.)."""
    code = models.CharField(max_length=30, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    ordre = models.IntegerField(default=1, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Type d'attestation"
        verbose_name_plural = "Types d'attestation"
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Attestation(models.Model):
    """Demande / enregistrement d'attestation à générer en PDF."""
    numero = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Numéro")
    type_attestation = models.ForeignKey(
        TypeAttestation,
        on_delete=models.PROTECT,
        related_name='attestations',
        verbose_name="Type d'attestation",
    )
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='attestations',
        verbose_name="Inscription",
    )
    date_delivrance = models.DateField(default=timezone.localdate, verbose_name="Date de délivrance")
    lieu_delivrance = models.CharField(
        max_length=200,
        default='Kinshasa',
        verbose_name="Lieu de délivrance",
    )
    objet = models.TextField(
        blank=True,
        null=True,
        verbose_name="Texte personnalisé",
        help_text="Remplace le texte standard si renseigné.",
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notes internes")
    fichier = models.FileField(
        upload_to=attestation_pdf_path,
        blank=True,
        null=True,
        verbose_name="Fichier PDF",
    )
    date_generation = models.DateTimeField(null=True, blank=True, verbose_name="Date de génération PDF")
    genere_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attestations_generees',
        verbose_name="Généré par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attestation"
        verbose_name_plural = "Attestations"
        ordering = ['-date_delivrance', '-created_at']

    def __str__(self):
        return f'{self.numero or "—"} — {self.type_attestation.nom}'

    @property
    def etudiant(self):
        return self.inscription.etudiant

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.numero:
            annee = self.inscription.annee_academique.code.replace('-', '')
            numero = f'ATT-{annee}-{self.pk:05d}'
            type(self).objects.filter(pk=self.pk).update(numero=numero)
            self.numero = numero
