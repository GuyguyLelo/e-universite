"""
Modèles pour la gestion des étudiants : Student, Inscription, Dossier, Pièces
"""
import os
import uuid

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from academics.models import Classe, AnneeAcademique
from .constants import NATIONALITE_CHOICES, NATIONALITE_DEFAULT
from .matricule import MATRICULE_REGEX, MATRICULE_HELP


def student_photo_path(instance, filename):
    """Génère le chemin pour les photos d'étudiants"""
    return f'students/photos/{instance.numero_etudiant}/{filename}'


def document_path(instance, filename):
    """Génère le chemin pour les documents étudiants"""
    return f'students/documents/{instance.etudiant.numero_etudiant}/{instance.type_document}/{filename}'


class Student(models.Model):
    """Modèle étudiant - étend le User Django"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile', null=True, blank=True, verbose_name="Utilisateur")
    etablissement = models.ForeignKey(
        'config.Etablissement',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='etudiants',
        verbose_name='Établissement',
    )
    numero_etudiant = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Numéro étudiant",
        validators=[RegexValidator(
            regex=MATRICULE_REGEX,
            message=f"Matricule invalide. {MATRICULE_HELP}",
        )],
    )
    code_unique = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Code unique",
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=200, verbose_name="Lieu de naissance")
    nationalite = models.CharField(
        max_length=100,
        choices=NATIONALITE_CHOICES,
        default=NATIONALITE_DEFAULT,
        verbose_name="Nationalité",
    )
    sexe = models.CharField(
        max_length=1,
        choices=[('M', 'Masculin'), ('F', 'Féminin')],
        verbose_name="Sexe"
    )
    telephone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Téléphone")
    email = models.EmailField(verbose_name="Email")
    adresse = models.TextField(blank=True, null=True, verbose_name="Adresse")
    photo = models.ImageField(upload_to=student_photo_path, blank=True, null=True, verbose_name="Photo")
    statut = models.CharField(
        max_length=20,
        choices=[
            ('actif', 'Actif'),
            ('suspendu', 'Suspendu'),
            ('exclu', 'Exclu'),
            ('diplome', 'Diplômé'),
            ('abandon', 'Abandon'),
        ],
        default='actif',
        verbose_name="Statut"
    )
    date_inscription = models.DateField(auto_now_add=True, verbose_name="Date d'inscription")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Étudiant"
        verbose_name_plural = "Étudiants"
        ordering = ['numero_etudiant']

    def __str__(self):
        return f"{self.numero_etudiant} - {self.prenom} {self.nom}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"

    @property
    def identite_cotation(self):
        """Libellé NOM - POSTNOM - PRÉNOM (postnom souvent stocké dans nom)."""
        nom_raw = (self.nom or '').strip()
        prenom = (self.prenom or '').strip()
        if prenom == '—':
            prenom = ''
        tokens = nom_raw.split(None, 1)
        nom = tokens[0] if tokens else '—'
        postnom = tokens[1] if len(tokens) > 1 else ''
        parts = [nom]
        if postnom:
            parts.append(postnom)
        if prenom:
            parts.append(prenom)
        return ' - '.join(parts)

    @classmethod
    def set_annee_active_context(cls, annee_pk):
        cls._annee_active_context = annee_pk

    @property
    def filiere_courante(self):
        """Filière de l'inscription de l'année active, ou la plus récente."""
        annee_active_pk = getattr(self.__class__, '_annee_active_context', None)
        if annee_active_pk is None:
            from academics.models import AnneeAcademique
            annee_active_pk = getattr(AnneeAcademique.get_active(), 'pk', None)

        inscriptions = list(self.inscriptions.all())

        if annee_active_pk:
            for ins in inscriptions:
                if ins.annee_academique_id == annee_active_pk and ins.classe_id:
                    promotion = getattr(ins.classe, 'promotion', None)
                    filiere = getattr(promotion, 'filiere', None) if promotion else None
                    if filiere:
                        return filiere

        inscriptions.sort(
            key=lambda i: getattr(getattr(i, 'annee_academique', None), 'annee_debut', 0),
            reverse=True,
        )
        for ins in inscriptions:
            if ins.classe_id:
                promotion = getattr(ins.classe, 'promotion', None)
                filiere = getattr(promotion, 'filiere', None) if promotion else None
                if filiere:
                    return filiere
        return None


INSCRIPTION_STATUTS_EXCLUS_LISTES = ('desinscrit', 'abandon')


class InscriptionQuerySet(models.QuerySet):
    def eligibles_listes(self):
        """Inscriptions visibles dans notes et délibérations (hors désinscrits / abandon)."""
        return self.exclude(statut__in=INSCRIPTION_STATUTS_EXCLUS_LISTES)

    def eligibles_grille_notes(self, semestre=None, session=None):
        """Inscriptions affichées sur la grille des notes (jury), paiements confirmés."""
        from finance.services import filtrer_inscriptions_en_ordre_paiement

        return filtrer_inscriptions_en_ordre_paiement(
            self.eligibles_listes().filter(classe__isnull=False),
            semestre=semestre,
            session=session,
        )


class Inscription(models.Model):
    """Inscription d'un étudiant à une classe (selon la hiérarchie section→filière→promotion→classe→local)"""
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='inscriptions', verbose_name="Étudiant")
    classe = models.ForeignKey(Classe, on_delete=models.PROTECT, related_name='inscriptions', verbose_name="Classe", null=True, blank=True)
    annee_academique = models.ForeignKey(AnneeAcademique, on_delete=models.CASCADE, related_name='inscriptions', verbose_name="Année académique")
    numero_inscription = models.CharField(max_length=50, unique=True, verbose_name="Numéro d'inscription")
    date_inscription = models.DateField(auto_now_add=True, verbose_name="Date d'inscription")
    statut = models.CharField(
        max_length=20,
        choices=[
            ('preinscrit', 'Pré-inscrit'),
            ('inscrit', 'Inscrit'),
            ('reinscrit', 'Réinscrit'),
            ('redoublant', 'Redoublant'),
            ('transfert', 'Transfert'),
            ('desinscrit', 'Désinscrit'),
            ('abandon', 'Abandon'),
        ],
        default='preinscrit',
        verbose_name="Statut"
    )
    frais_inscription = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Frais d'inscription")
    frais_payes = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Frais payés")
    en_ordre_paiement = models.BooleanField(default=False, verbose_name="En ordre de paiement")
    dossier_complet = models.BooleanField(default=False, verbose_name="Dossier complet")
    date_abandon = models.DateField(null=True, blank=True, verbose_name="Date d'abandon")
    motif_abandon = models.TextField(blank=True, null=True, verbose_name="Motif d'abandon")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InscriptionQuerySet.as_manager()

    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        unique_together = [['etudiant', 'classe', 'annee_academique']]
        ordering = ['-annee_academique', 'etudiant']

    def __str__(self):
        return f"{self.etudiant.numero_etudiant} - {self.classe} ({self.annee_academique.code})"

    @property
    def promotion(self):
        return self.classe.promotion

    @property
    def filiere(self):
        return self.classe.promotion.filiere

    @property
    def section(self):
        return self.classe.promotion.filiere.section

    @property
    def local(self):
        return self.classe.local

    @property
    def solde_frais(self):
        return self.frais_inscription - self.frais_payes


class TypeDocument(models.Model):
    """Types de documents requis (ex: Baccalauréat, Relevé de notes, etc.)"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    obligatoire = models.BooleanField(default=True, verbose_name="Obligatoire")
    ordre = models.IntegerField(default=1, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Type de document"
        verbose_name_plural = "Types de documents"
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class DocumentEtudiant(models.Model):
    """Document fourni par un étudiant"""
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents', verbose_name="Étudiant")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='documents', null=True, blank=True, verbose_name="Inscription")
    type_document = models.ForeignKey(TypeDocument, on_delete=models.CASCADE, related_name='documents', verbose_name="Type de document")
    fichier = models.FileField(upload_to=document_path, blank=True, null=True, verbose_name="Fichier")
    date_depot = models.DateField(auto_now_add=True, verbose_name="Date de dépôt")
    valide = models.BooleanField(default=False, verbose_name="Validé")
    date_validation = models.DateField(null=True, blank=True, verbose_name="Date de validation")
    valide_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Validé par")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Document étudiant"
        verbose_name_plural = "Documents étudiants"
        ordering = ['-date_depot']

    def __str__(self):
        return f"{self.etudiant.numero_etudiant} - {self.type_document.nom}"


class DossierEtudiant(models.Model):
    """Dossier administratif complet d'un étudiant pour une inscription"""
    inscription = models.OneToOneField(Inscription, on_delete=models.CASCADE, related_name='dossier', verbose_name="Inscription")
    date_ouverture = models.DateField(auto_now_add=True, verbose_name="Date d'ouverture")
    date_fermeture = models.DateField(null=True, blank=True, verbose_name="Date de fermeture")
    statut = models.CharField(
        max_length=20,
        choices=[
            ('en_cours', 'En cours'),
            ('complet', 'Complet'),
            ('incomplet', 'Incomplet'),
            ('valide', 'Validé'),
            ('rejete', 'Rejeté'),
        ],
        default='en_cours',
        verbose_name="Statut"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier étudiant"
        verbose_name_plural = "Dossiers étudiants"
        ordering = ['-date_ouverture']

    def __str__(self):
        return f"Dossier - {self.inscription.etudiant.numero_etudiant} ({self.inscription.annee_academique.code})"

    def verifier_completude(self):
        """Vérifie si tous les documents obligatoires ont été déposés."""
        from .dossier import documents_obligatoires_deposes

        complet, _, _ = documents_obligatoires_deposes(self.inscription)

        if complet:
            self.statut = 'complet'
            self.inscription.dossier_complet = True
        else:
            self.statut = 'incomplet'
            self.inscription.dossier_complet = False

        self.save(update_fields=['statut', 'updated_at'])
        self.inscription.save(update_fields=['dossier_complet', 'updated_at'])
        return complet
