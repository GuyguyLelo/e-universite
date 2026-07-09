"""
Modèles pour les délibérations : Délibération, Décision, Paramètres LMD
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from academics.models import Semestre, Promotion, AnneeAcademique
from students.models import Inscription, Student
from evaluations.models import Session
from decimal import Decimal


class ParametresLMD(models.Model):
    """Paramètres de configuration LMD (seuils, compensation, etc.)"""
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='parametres_lmd', verbose_name="Promotion")
    seuil_validation = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Seuil de validation (/20)"
    )
    compensation_intra_ue = models.BooleanField(default=True, verbose_name="Compensation intra-UE")
    compensation_intra_semestre = models.BooleanField(default=True, verbose_name="Compensation intra-semestre")
    compensation_annuelle = models.BooleanField(default=True, verbose_name="Compensation annuelle")
    capitalisation_ue = models.BooleanField(default=True, verbose_name="Capitalisation des UE")
    capitalisation_ec = models.BooleanField(default=True, verbose_name="Capitalisation des EC")
    passage_avec_dettes = models.BooleanField(default=True, verbose_name="Passage avec dettes")
    seuil_credits_minimum = models.IntegerField(default=30, validators=[MinValueValidator(0)], verbose_name="Seuil crédits minimum pour passage")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres LMD"
        verbose_name_plural = "Paramètres LMD"
        unique_together = [['promotion']]

    def __str__(self):
        return f"Paramètres LMD - {self.promotion.code}"


class Deliberation(models.Model):
    """Délibération d'un jury (semestrielle, annuelle S1+S2 ou cycle Master M1+M2)."""
    TYPE_SEMESTRIELLE = 'semestrielle'
    TYPE_ANNUELLE = 'annuelle'
    TYPE_CYCLE_MASTER = 'cycle_master'
    TYPE_CHOICES = [
        (TYPE_SEMESTRIELLE, 'Semestrielle'),
        (TYPE_ANNUELLE, 'Annuelle'),
        (TYPE_CYCLE_MASTER, 'Cycle Master (M1+M2)'),
    ]

    type_deliberation = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_SEMESTRIELLE,
        verbose_name="Type",
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='deliberations',
        null=True,
        blank=True,
        verbose_name="Session",
    )
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='deliberations', verbose_name="Promotion")
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='deliberations_annuelles',
        null=True,
        blank=True,
        verbose_name="Année académique",
    )
    annee_academique_m1 = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='deliberations_cycle_m1',
        null=True,
        blank=True,
        verbose_name="Année académique Master 1",
    )
    semestre1 = models.ForeignKey(
        Semestre,
        on_delete=models.CASCADE,
        related_name='deliberations_annuelles_s1',
        null=True,
        blank=True,
        verbose_name="Semestre 1",
    )
    semestre2 = models.ForeignKey(
        Semestre,
        on_delete=models.CASCADE,
        related_name='deliberations_annuelles_s2',
        null=True,
        blank=True,
        verbose_name="Semestre 2",
    )
    date_deliberation = models.DateField(verbose_name="Date de délibération")
    president_jury = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliberations_president', verbose_name="Président du jury")
    president_jury_nom = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nom affiché du président",
    )
    secretaire_jury_nom = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Secrétaire du jury",
    )
    membres_jury = models.ManyToManyField(User, related_name='deliberations_membre', blank=True, verbose_name="Membres du jury")
    membres_jury_noms = models.TextField(
        blank=True,
        verbose_name="Membres du jury (noms libres)",
        help_text="Un nom par ligne (affiché dans la fiche délibération et le PV).",
    )
    statut = models.CharField(
        max_length=20,
        choices=[
            ('en_preparation', 'En préparation'),
            ('en_cours', 'En cours'),
            ('terminee', 'Terminée'),
            ('verrouillee', 'Verrouillée'),
        ],
        default='en_preparation',
        verbose_name="Statut"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notes du jury")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Délibération"
        verbose_name_plural = "Délibérations"
        ordering = ['-date_deliberation']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'promotion'],
                condition=models.Q(type_deliberation='semestrielle'),
                name='delib_unique_session_promotion',
            ),
            models.UniqueConstraint(
                fields=['promotion', 'annee_academique', 'semestre1', 'semestre2'],
                condition=models.Q(type_deliberation='annuelle'),
                name='delib_unique_annuelle',
            ),
            models.UniqueConstraint(
                fields=['promotion', 'annee_academique_m1', 'annee_academique'],
                condition=models.Q(type_deliberation='cycle_master'),
                name='delib_unique_cycle_master',
            ),
        ]

    def __str__(self):
        if self.type_deliberation == self.TYPE_CYCLE_MASTER:
            a1 = self.annee_academique_m1.code if self.annee_academique_m1 else '?'
            a2 = self.annee_academique.code if self.annee_academique else '?'
            return f"Délibération cycle M1+M2 ({a1}/{a2}) — {self.promotion.code} ({self.date_deliberation})"
        if self.type_deliberation == self.TYPE_ANNUELLE:
            s1 = self.semestre1.code if self.semestre1 else '?'
            s2 = self.semestre2.code if self.semestre2 else '?'
            return f"Délibération annuelle {s1}+{s2} — {self.promotion.code} ({self.date_deliberation})"
        code = self.session.code if self.session else '—'
        return f"Délibération - {code} ({self.date_deliberation})"

    @property
    def libelle_court(self):
        if self.type_deliberation == self.TYPE_CYCLE_MASTER:
            return 'Cycle Master M1+M2'
        if self.type_deliberation == self.TYPE_ANNUELLE:
            return f"Annuelle {self.semestre1.code}+{self.semestre2.code}"
        return self.session.code if self.session else '—'

    @property
    def est_agregee(self):
        """Délibération multi-périodes (annuelle ou cycle Master)."""
        return self.type_deliberation in (self.TYPE_ANNUELLE, self.TYPE_CYCLE_MASTER)

    @property
    def libelle_periode1(self):
        if self.type_deliberation == self.TYPE_CYCLE_MASTER:
            return 'Master 1'
        if self.semestre1:
            return self.semestre1.code
        return '—'

    @property
    def libelle_periode2(self):
        if self.type_deliberation == self.TYPE_CYCLE_MASTER:
            return 'Master 2'
        if self.semestre2:
            return self.semestre2.code
        return '—'

    @property
    def libelle_moyenne_globale(self):
        if self.type_deliberation == self.TYPE_CYCLE_MASTER:
            return 'Moy. cycle'
        if self.type_deliberation == self.TYPE_ANNUELLE:
            return 'Moy. annuelle'
        return 'Moyenne'

    @property
    def composition_bureau(self) -> dict:
        from deliberations.jury_bureau import resoudre_composition_bureau
        return resoudre_composition_bureau(self)


class DecisionJury(models.Model):
    """Décision du jury pour un étudiant lors d'une délibération"""
    deliberation = models.ForeignKey(Deliberation, on_delete=models.CASCADE, related_name='decisions', verbose_name="Délibération")
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='decisions_jury', verbose_name="Étudiant")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='decisions_jury', verbose_name="Inscription")
    decision = models.CharField(
        max_length=20,
        choices=[
            ('admis', 'Admis'),
            ('admis_compensation', 'Admis par compensation'),
            ('admis_avec_dettes', 'Admis avec dettes'),
            ('defaillant', 'Défaillant'),
            ('redouble', 'Redouble'),
            ('exclu', 'Exclu'),
            ('ajourne', 'Ajourné'),
            ('report', 'Report'),
        ],
        verbose_name="Décision"
    )
    moyenne_semestre = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Moyenne du semestre / annuelle",
    )
    moyenne_semestre1 = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Moyenne semestre 1",
    )
    moyenne_semestre2 = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Moyenne semestre 2",
    )
    credits_semestre1 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits semestre 1",
    )
    credits_semestre2 = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits semestre 2",
    )
    credits_obtenus = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits obtenus"
    )
    credits_totaux = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits totaux"
    )
    rang = models.IntegerField(null=True, blank=True, verbose_name="Rang")
    mention = models.CharField(
        max_length=20,
        choices=[
            ('', 'Sans mention'),
            ('passable', 'Passable'),
            ('assez_bien', 'Assez Bien'),
            ('bien', 'Bien'),
            ('tres_bien', 'Très Bien'),
        ],
        blank=True,
        verbose_name="Mention"
    )
    notes_jury = models.TextField(blank=True, null=True, verbose_name="Notes du jury")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Décision du jury"
        verbose_name_plural = "Décisions du jury"
        unique_together = [['deliberation', 'etudiant']]
        ordering = ['deliberation', 'rang', 'etudiant']

    def __str__(self):
        ref = self.deliberation.libelle_court
        return f"{self.etudiant.numero_etudiant} - {self.decision} ({ref})"
