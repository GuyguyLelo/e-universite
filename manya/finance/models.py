from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from academics.models import AnneeAcademique, Semestre
from students.models import Inscription


class MotifPaiement(models.Model):
    """Motif d'enrôlement session — commun aux filières CSI et RX."""

    FILIERES_ENROLLEMENT = ('CSI', 'RX')

    CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE = 'enrollement_session_principale'
    CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE = 'enrollement_session_rattrapage'

    CONTEXTE_CHOICES = [
        (CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE, 'Enrôlement session principale'),
        (CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE, 'Enrôlement session rattrapage'),
    ]

    DEVISE_USD = 'USD'
    DEVISE_CDF = 'CDF'
    DEVISE_CHOICES = [
        (DEVISE_USD, 'Dollars (USD)'),
        (DEVISE_CDF, 'Francs congolais (CDF)'),
    ]

    CODE_SUFFIXES = {
        CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE: 'PRINC',
        CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE: 'RATT',
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
            'semestre__numero',
            'contexte',
            'ordre',
            'nom',
        ]
        unique_together = [['annee_academique', 'semestre', 'contexte']]

    def __str__(self):
        return (
            f'{self.annee_academique.code} — {self.semestre.code} — '
            f'{self.get_contexte_display()} — {self.nom}'
        )

    @property
    def portee_libelle(self):
        return 'CSI et RX'

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
        semestre_code = semestre.code if hasattr(semestre, 'code') else f'S{semestre}'
        return f'{semestre_code}-{suffix}'[:20]

    @classmethod
    def build_nom(cls, semestre, contexte) -> str:
        libelles = dict(cls.CONTEXTE_CHOICES)
        semestre_code = semestre.code if hasattr(semestre, 'code') else str(semestre)
        return f'{libelles.get(contexte, contexte)} — {semestre_code}'[:200]

    def save(self, *args, **kwargs):
        if self.semestre_id and self.contexte:
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
        if not self.semestre_id:
            raise ValidationError({'semestre': 'Le semestre est obligatoire.'})
        if self.annee_academique_id and self.semestre_id and self.contexte:
            conflit = MotifPaiement.objects.filter(
                annee_academique_id=self.annee_academique_id,
                semestre_id=self.semestre_id,
                contexte=self.contexte,
            ).exclude(pk=self.pk).exists()
            if conflit:
                raise ValidationError(
                    'Un motif existe déjà pour ce semestre et ce type de session.'
                )


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
