from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from academics.models import AnneeAcademique, Semestre
from students.models import Inscription


class MotifPaiement(models.Model):
    """Motif d'enrôlement session, pour toutes les filières de l'établissement."""

    CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE = 'enrollement_session_principale'
    CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE = 'enrollement_session_rattrapage'
    CONTEXTE_FRAIS_INSCRIPTION = 'frais_inscription'
    CONTEXTE_ACAD_RECRUTEMENT = 'acad_recrutement'
    CONTEXTE_ACAD_MONTANTES_1 = 'acad_montantes_1'
    CONTEXTE_ACAD_MONTANTES_2 = 'acad_montantes_2'
    CONTEXTE_ACAD_ETRANGER_REC = 'acad_etranger_rec'
    CONTEXTE_ACAD_ETRANGER_1 = 'acad_etranger_1'
    CONTEXTE_ACAD_ETRANGER_2 = 'acad_etranger_2'

    CONTEXTE_CHOICES = [
        (CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE, 'Enrôlement session principale'),
        (CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE, 'Enrôlement session rattrapage'),
        (CONTEXTE_FRAIS_INSCRIPTION, "Frais d'inscription"),
        (CONTEXTE_ACAD_RECRUTEMENT, 'Frais académiques — classes de recrutement'),
        (CONTEXTE_ACAD_MONTANTES_1, 'Frais académiques — classes montantes, 1re tranche'),
        (CONTEXTE_ACAD_MONTANTES_2, 'Frais académiques — classes montantes, 2e tranche'),
        (CONTEXTE_ACAD_ETRANGER_REC, 'Frais académiques étrangers — recrutement'),
        (CONTEXTE_ACAD_ETRANGER_1, 'Frais académiques étrangers — 1re tranche'),
        (CONTEXTE_ACAD_ETRANGER_2, 'Frais académiques étrangers — 2e tranche'),
    ]

    CONTEXTES_ANNUELS = {
        CONTEXTE_FRAIS_INSCRIPTION,
        CONTEXTE_ACAD_RECRUTEMENT,
        CONTEXTE_ACAD_MONTANTES_1,
        CONTEXTE_ACAD_MONTANTES_2,
        CONTEXTE_ACAD_ETRANGER_REC,
        CONTEXTE_ACAD_ETRANGER_1,
        CONTEXTE_ACAD_ETRANGER_2,
    }

    DEVISE_USD = 'USD'
    DEVISE_CDF = 'CDF'
    DEVISE_CHOICES = [
        (DEVISE_USD, 'Dollars (USD)'),
        (DEVISE_CDF, 'Francs congolais (CDF)'),
    ]

    CODE_SUFFIXES = {
        CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE: 'PRINC',
        CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE: 'RATT',
        CONTEXTE_FRAIS_INSCRIPTION: 'INSCR',
        CONTEXTE_ACAD_RECRUTEMENT: 'ACAD-REC',
        CONTEXTE_ACAD_MONTANTES_1: 'ACAD-M1',
        CONTEXTE_ACAD_MONTANTES_2: 'ACAD-M2',
        CONTEXTE_ACAD_ETRANGER_REC: 'ACAD-EREC',
        CONTEXTE_ACAD_ETRANGER_1: 'ACAD-E1',
        CONTEXTE_ACAD_ETRANGER_2: 'ACAD-E2',
    }
    ORDRES_DEFAUT = {
        CONTEXTE_FRAIS_INSCRIPTION: 10,
        CONTEXTE_ACAD_RECRUTEMENT: 20,
        CONTEXTE_ACAD_MONTANTES_1: 21,
        CONTEXTE_ACAD_MONTANTES_2: 22,
        CONTEXTE_ACAD_ETRANGER_REC: 30,
        CONTEXTE_ACAD_ETRANGER_1: 31,
        CONTEXTE_ACAD_ETRANGER_2: 32,
    }

    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='motifs_paiement',
        verbose_name='Année académique',
    )
    semestre = models.ForeignKey(
        Semestre,
        on_delete=models.CASCADE,
        related_name='motifs_paiement',
        verbose_name='Semestre',
        null=True,
        blank=True,
        help_text="Laissé vide pour un frais annuel (inscription, frais académiques).",
    )
    contexte = models.CharField(
        max_length=40,
        choices=CONTEXTE_CHOICES,
        default=CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE,
        verbose_name='Contexte',
    )
    code = models.CharField(max_length=20, verbose_name='Code', editable=False)
    nom = models.CharField(max_length=200, verbose_name='Nom')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Montant',
        help_text='0 = montant variable selon le cas',
    )
    devise = models.CharField(
        max_length=3,
        choices=DEVISE_CHOICES,
        default=DEVISE_USD,
        verbose_name='Devise',
    )
    ordre = models.PositiveIntegerField(default=1, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Motif de paiement'
        verbose_name_plural = 'Motifs de paiement'
        ordering = [
            'annee_academique__annee_debut',
            'ordre',
            'semestre__numero',
            'contexte',
            'nom',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['annee_academique', 'semestre', 'contexte'],
                condition=models.Q(semestre__isnull=False),
                name='finance_motif_unique_semestre',
            ),
            models.UniqueConstraint(
                fields=['annee_academique', 'contexte'],
                condition=models.Q(semestre__isnull=True),
                name='finance_motif_unique_annuel',
            ),
        ]

    def __str__(self):
        periode = self.semestre.code if self.semestre_id else 'Annuel'
        return (
            f'{self.annee_academique.code} — {periode} — '
            f'{self.get_contexte_display()} — {self.nom}'
        )

    @property
    def portee_libelle(self):
        return 'Toutes les filières'

    @property
    def libelle_court(self) -> str:
        """Libellé pour listes et filtres (ex. S8-PRINC · Enrôlement session principale)."""
        return f'{self.code} · {self.get_contexte_display()}'

    @property
    def montant_affiche(self) -> str:
        if not self.montant:
            return 'Variable'
        if self.devise == self.DEVISE_CDF:
            return f'{self.montant:,.0f} CDF'.replace(',', ' ')
        return f'{self.montant:.2f} USD'

    @classmethod
    def build_code(cls, semestre, contexte) -> str:
        suffix = cls.CODE_SUFFIXES.get(contexte, 'MOTIF')
        if contexte in cls.CONTEXTES_ANNUELS or semestre is None:
            return suffix[:20]
        semestre_code = semestre.code if hasattr(semestre, 'code') else f'S{semestre}'
        return f'{semestre_code}-{suffix}'[:20]

    @classmethod
    def build_nom(cls, semestre, contexte) -> str:
        libelles = dict(cls.CONTEXTE_CHOICES)
        if contexte in cls.CONTEXTES_ANNUELS:
            return libelles.get(contexte, contexte)[:200]
        semestre_code = semestre.code if hasattr(semestre, 'code') else str(semestre)
        return f'{libelles.get(contexte, contexte)} — {semestre_code}'[:200]

    def save(self, *args, **kwargs):
        if self.contexte in self.CONTEXTES_ANNUELS:
            self.semestre = None
            self.code = self.build_code(None, self.contexte)
            if not self.nom:
                self.nom = self.build_nom(None, self.contexte)
            if not self.ordre:
                self.ordre = self.ORDRES_DEFAUT.get(self.contexte, 10)
        elif self.semestre_id and self.contexte:
            semestre = self.semestre
            if semestre is None:
                semestre = Semestre.objects.get(pk=self.semestre_id)
            self.code = self.build_code(semestre, self.contexte)
            if not self.nom:
                self.nom = self.build_nom(semestre, self.contexte)
            if self.contexte == self.CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE:
                self.ordre = self.ordre or 2
            elif not self.ordre:
                self.ordre = 1
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.contexte in self.CONTEXTES_ANNUELS:
            self.semestre = None
        elif not self.semestre_id:
            raise ValidationError({'semestre': 'Le semestre est obligatoire pour un enrôlement.'})
        if self.annee_academique_id and self.contexte:
            conflit = MotifPaiement.objects.filter(
                annee_academique_id=self.annee_academique_id,
                contexte=self.contexte,
            )
            if self.semestre_id:
                conflit = conflit.filter(semestre_id=self.semestre_id)
            else:
                conflit = conflit.filter(semestre__isnull=True)
            if conflit.exclude(pk=self.pk).exists():
                raise ValidationError('Un motif existe déjà pour cette année et ce frais.')


class ConfirmationPaiement(models.Model):
    """Confirmation qu'un motif de paiement est réglé pour une inscription."""

    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='confirmations_paiement',
        verbose_name='Inscription',
    )
    motif_paiement = models.ForeignKey(
        MotifPaiement,
        on_delete=models.CASCADE,
        related_name='confirmations',
        verbose_name='Motif de paiement',
    )
    confirme = models.BooleanField(default=True, verbose_name='Confirmé')
    date_confirmation = models.DateTimeField(auto_now=True, verbose_name='Date de confirmation')
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmations_paiement_effectuees',
        verbose_name='Confirmé par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Confirmation de paiement'
        verbose_name_plural = 'Confirmations de paiement'
        unique_together = [['inscription', 'motif_paiement']]
        ordering = ['-date_confirmation']

    def __str__(self):
        return f'{self.inscription} — {self.motif_paiement.code}'


class Paiement(models.Model):
    """Encaissement d'un frais étudiant : caisse, mobile money ou carte bancaire."""

    MODE_ESPECES = 'especes'
    MODE_MOBILE_MONEY = 'mobile_money'
    MODE_CARTE = 'carte_bancaire'
    MODE_CHOICES = [
        (MODE_ESPECES, 'Espèces (caisse)'),
        (MODE_MOBILE_MONEY, 'Mobile money'),
        (MODE_CARTE, 'Carte bancaire'),
    ]

    OPERATEUR_AIRTEL = 'airtel_money'
    OPERATEUR_MPESA = 'm_pesa'
    OPERATEUR_ORANGE = 'orange_money'
    OPERATEUR_AFRIMONEY = 'afrimoney'
    OPERATEUR_CHOICES = [
        (OPERATEUR_AIRTEL, 'Airtel Money'),
        (OPERATEUR_MPESA, 'M-Pesa'),
        (OPERATEUR_ORANGE, 'Orange Money'),
        (OPERATEUR_AFRIMONEY, 'Afrimoney'),
    ]

    STATUT_PAYE = 'paye'
    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_ECHOUE = 'echoue'
    STATUT_ANNULE = 'annule'
    STATUT_CHOICES = [
        (STATUT_PAYE, 'Payé'),
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_ECHOUE, 'Échoué'),
        (STATUT_ANNULE, 'Annulé'),
    ]

    reference = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
        verbose_name='Référence',
    )
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.PROTECT,
        related_name='paiements',
        verbose_name='Inscription',
    )
    motif_paiement = models.ForeignKey(
        MotifPaiement,
        on_delete=models.PROTECT,
        related_name='paiements',
        verbose_name='Frais',
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Montant')
    devise = models.CharField(
        max_length=3,
        choices=MotifPaiement.DEVISE_CHOICES,
        default=MotifPaiement.DEVISE_USD,
        verbose_name='Devise',
    )
    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=MODE_ESPECES,
        verbose_name='Mode de paiement',
    )
    operateur = models.CharField(
        max_length=20,
        choices=OPERATEUR_CHOICES,
        blank=True,
        verbose_name='Opérateur mobile money',
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Numéro mobile money',
    )
    reference_transaction = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Référence de transaction',
        help_text='Code reçu par mobile money ou autorisation de la carte.',
    )
    carte_masquee = models.CharField(
        max_length=4,
        blank=True,
        verbose_name='4 derniers chiffres',
        help_text='Uniquement les 4 derniers chiffres. Le numéro complet n\'est jamais enregistré.',
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_PAYE,
        verbose_name='Statut',
    )
    date_paiement = models.DateTimeField(default=timezone.now, verbose_name='Date du paiement')
    observation = models.TextField(blank=True, verbose_name='Observation')
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements_enregistres',
        verbose_name='Enregistré par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date_paiement', '-pk']
        indexes = [
            models.Index(fields=['statut', 'mode']),
            models.Index(fields=['date_paiement']),
        ]

    def __str__(self):
        return f'{self.reference} — {self.montant} {self.devise}'

    @property
    def montant_affiche(self) -> str:
        if self.devise == MotifPaiement.DEVISE_CDF:
            return f'{self.montant:,.0f} CDF'.replace(',', ' ')
        return f'{self.montant:.2f} USD'

    @classmethod
    def prochaine_reference(cls, annee_code: str) -> str:
        prefix = f'PAY-{annee_code}-'
        derniere = (
            cls.objects.filter(reference__startswith=prefix)
            .order_by('-reference')
            .values_list('reference', flat=True)
            .first()
        )
        numero = 1
        if derniere:
            try:
                numero = int(derniere.rsplit('-', 1)[-1]) + 1
            except ValueError:
                numero = cls.objects.filter(reference__startswith=prefix).count() + 1
        return f'{prefix}{numero:05d}'

    def save(self, *args, **kwargs):
        if not self.reference:
            annee = ''
            if self.inscription_id:
                annee = self.inscription.annee_academique.code
            self.reference = self.prochaine_reference(annee or '0000')
        if self.mode != self.MODE_MOBILE_MONEY:
            self.operateur = ''
            self.telephone = ''
        if self.mode != self.MODE_CARTE:
            self.carte_masquee = ''
        if self.mode == self.MODE_ESPECES:
            self.reference_transaction = ''
        super().save(*args, **kwargs)
