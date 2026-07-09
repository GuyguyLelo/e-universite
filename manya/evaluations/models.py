"""
Modèles pour la gestion des évaluations : Evaluation, Note, Session
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from academics.models import AnneeAcademique, ElementConstitutif, UniteEnseignement, Semestre
from students.models import Inscription, Student
from decimal import Decimal


# Ancien code « Contrôle continu » — remplacé par TJ (travaux journaliers) dans la fiche de cotation.
TYPE_EVALUATION_CODES_FORMULAIRE_EXCLUS = frozenset({'CC'})


class TypeEvaluation(models.Model):
    """Types d'évaluation (TJ, TP, Examen, Rattrapage, etc.)"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Coefficient par défaut"
    )
    note_max = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Note maximale"
    )
    ordre = models.IntegerField(default=1, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Type d'évaluation"
        verbose_name_plural = "Types d'évaluation"
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom

    @classmethod
    def pour_formulaire_evaluation(cls, inclure_pk=None):
        """Types proposés à la création / modification d'une évaluation."""
        from django.db.models import Q

        qs = cls.objects.filter(active=True).exclude(
            code__in=TYPE_EVALUATION_CODES_FORMULAIRE_EXCLUS,
        )
        if inclure_pk:
            qs = cls.objects.filter(Q(pk__in=qs.values('pk')) | Q(pk=inclure_pk))
        return qs.order_by('ordre', 'nom')


class Session(models.Model):
    """Session d'évaluation (Session 1, Session 2/Rattrapage)"""
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='sessions_evaluation',
        verbose_name="Année académique",
    )
    semestre = models.ForeignKey(Semestre, on_delete=models.CASCADE, related_name='sessions', verbose_name="Semestre")
    numero = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)], verbose_name="Numéro de session")
    code = models.CharField(max_length=50, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    date_deliberation = models.DateField(null=True, blank=True, verbose_name="Date de délibération")
    deliberation_faite = models.BooleanField(default=False, verbose_name="Délibération effectuée")
    verrouillee = models.BooleanField(default=False, verbose_name="Session verrouillée")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        unique_together = [['semestre', 'numero', 'annee_academique']]
        ordering = ['-annee_academique__annee_debut', 'semestre', 'numero']

    def __str__(self):
        return f"{self.code} - {self.nom}"

    @classmethod
    def pour_annee(cls, annee=None):
        """Sessions filtrées par année académique (année active par défaut)."""
        qs = cls.objects.select_related('semestre', 'annee_academique')
        annee = annee or AnneeAcademique.get_active()
        if annee:
            qs = qs.filter(annee_academique=annee)
        return qs

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"{self.semestre.code}-S{self.numero}"
        if not self.nom:
            self.nom = f"Session {self.numero} - {self.semestre.nom}"
        super().save(*args, **kwargs)


class Evaluation(models.Model):
    """Évaluation d'un EC (ex: CC de Mathématiques)"""
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='evaluations',
        verbose_name="Année académique",
    )
    ec = models.ForeignKey(ElementConstitutif, on_delete=models.CASCADE, related_name='evaluations', verbose_name="Élément Constitutif")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='evaluations', verbose_name="Session")
    type_evaluation = models.ForeignKey(TypeEvaluation, on_delete=models.CASCADE, related_name='evaluations', verbose_name="Type d'évaluation")
    code = models.CharField(max_length=50, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    date_evaluation = models.DateField(verbose_name="Date d'évaluation")
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Coefficient"
    )
    note_max = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Note maximale"
    )
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluations_responsable', verbose_name="Responsable")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        unique_together = [['ec', 'session', 'type_evaluation']]
        ordering = ['session', 'ec', 'type_evaluation']

    def __str__(self):
        return f"{self.code} - {self.nom}"

    @staticmethod
    def build_code(ec, session, type_evaluation) -> str:
        return f"{ec.code}-{session.code}-{type_evaluation.code}"[:50]

    @staticmethod
    def build_nom(type_evaluation, ec, session=None) -> str:
        from evaluations.calcul_notes import est_type_exam, est_type_rattrapage, est_type_tj

        if est_type_tj(type_evaluation):
            return f'TJ - {ec.nom}'[:200]
        if est_type_exam(type_evaluation) or est_type_rattrapage(type_evaluation):
            suffix = 'SR' if session is not None and session.numero != 1 else 'SP'
            return f'Examen {ec.nom} ({suffix})'[:200]
        return f'{type_evaluation.nom} - {ec.nom}'[:200]

    def save(self, *args, **kwargs):
        if self.session_id:
            self.annee_academique_id = self.session.annee_academique_id
        if not self.code:
            self.code = self.build_code(self.ec, self.session, self.type_evaluation)
        if not self.nom:
            self.nom = self.build_nom(self.type_evaluation, self.ec, self.session)
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.session_id and self.annee_academique_id:
            if self.session.annee_academique_id != self.annee_academique_id:
                raise ValidationError(
                    "L'année académique de l'évaluation doit correspondre à celle de la session."
                )


class Note(models.Model):
    """Note d'un étudiant à une évaluation"""
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes', verbose_name="Étudiant")
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='notes_etudiants', verbose_name="Évaluation")
    note = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Note (/20)"
    )
    note_sur = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Note sur"
    )
    absent = models.BooleanField(default=False, verbose_name="Absent")
    justifie = models.BooleanField(default=False, verbose_name="Absence justifiée")
    justificatif = models.TextField(blank=True, null=True, verbose_name="Justificatif")
    saisie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes_saisies', verbose_name="Saisie par")
    date_saisie = models.DateTimeField(auto_now_add=True, verbose_name="Date de saisie")
    modifie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes_modifiees', related_query_name='note_modifiee', verbose_name="Modifié par")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        unique_together = [['etudiant', 'evaluation']]
        ordering = ['-date_saisie']

    def __str__(self):
        if self.absent:
            return f"{self.etudiant.numero_etudiant} - {self.evaluation.code} : Absent"
        return f"{self.etudiant.numero_etudiant} - {self.evaluation.code} : {self.note}/20"

    @property
    def note_finale(self):
        """Calcule la note finale en tenant compte de la note sur"""
        if self.absent or self.note is None:
            return None
        if self.note_sur and self.note_sur != Decimal('20.00'):
            # Conversion proportionnelle sur 20
            return (self.note / self.note_sur) * Decimal('20.00')
        return self.note

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.absent and self.note is None:
            raise ValidationError("Une note doit être saisie si l'étudiant n'est pas absent")


class NoteEC(models.Model):
    """Note finale d'un étudiant à un EC (moyenne TJ + examen du semestre, ou pondérée)"""
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes_ec', verbose_name="Étudiant")
    ec = models.ForeignKey(ElementConstitutif, on_delete=models.CASCADE, related_name='notes_etudiants', verbose_name="Élément Constitutif")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='notes_ec', verbose_name="Session")
    note_finale = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Note finale (/20)"
    )
    credits_obtenus = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits obtenus"
    )
    valide = models.BooleanField(default=False, verbose_name="EC validé")
    capitalise = models.BooleanField(default=False, verbose_name="EC capitalisé")
    calculee_auto = models.BooleanField(default=True, verbose_name="Calculée automatiquement")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Note EC"
        verbose_name_plural = "Notes EC"
        unique_together = [['etudiant', 'ec', 'session']]
        ordering = ['session', 'ec', 'etudiant']

    def __str__(self):
        return f"{self.etudiant.numero_etudiant} - {self.ec.code} : {self.note_finale}/20"


class NoteUE(models.Model):
    """Note finale d'un étudiant à une UE (moyenne pondérée des EC)"""
    etudiant = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes_ue', verbose_name="Étudiant")
    ue = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE, related_name='notes_etudiants', verbose_name="Unité d'Enseignement")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='notes_ue', verbose_name="Session")
    note_finale = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Note finale (/20)"
    )
    credits_obtenus = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Crédits obtenus"
    )
    valide = models.BooleanField(default=False, verbose_name="UE validée")
    capitalise = models.BooleanField(default=False, verbose_name="UE capitalisée")
    calculee_auto = models.BooleanField(default=True, verbose_name="Calculée automatiquement")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Note UE"
        verbose_name_plural = "Notes UE"
        unique_together = [['etudiant', 'ue', 'session']]
        ordering = ['session', 'ue', 'etudiant']

    def __str__(self):
        return f"{self.etudiant.numero_etudiant} - {self.ue.code} : {self.note_finale}/20"
