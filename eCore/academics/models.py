"""
Modèles pour la structure académique (e-Université) :
Section → Filière → Promotion → Classe → Local

+ Modèles LMD : Semestre, UE, EC
"""
from django.db import models, transaction
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Section(models.Model):
    """Section (ex: Licence, Master), rattachée à un établissement."""
    etablissement = models.ForeignKey(
        'config.Etablissement',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sections',
        verbose_name='Établissement',
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"
        ordering = ['etablissement', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['code'],
                condition=models.Q(etablissement__isnull=True),
                name='uniq_section_code_sans_etablissement',
            ),
            models.UniqueConstraint(
                fields=['etablissement', 'code'],
                condition=models.Q(etablissement__isnull=False),
                name='uniq_section_code_par_etablissement',
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.nom}"


class Faculte(models.Model):
    """Faculté d'un établissement (ex. les facultés de l'UNIKIN)."""
    etablissement = models.ForeignKey(
        'config.Etablissement',
        on_delete=models.PROTECT,
        related_name='facultes',
        verbose_name='Établissement',
    )
    code = models.CharField(max_length=20, verbose_name='Sigle')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    active = models.BooleanField(default=True, verbose_name='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Faculté'
        verbose_name_plural = 'Facultés'
        ordering = ['etablissement_id', 'nom']
        constraints = [
            models.UniqueConstraint(
                fields=['etablissement', 'code'],
                name='uniq_faculte_code_par_etablissement',
            ),
        ]

    def __str__(self):
        return f'{self.code} — {self.nom}'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class Departement(models.Model):
    """Département (mention) rattaché à une faculté."""
    faculte = models.ForeignKey(
        Faculte,
        on_delete=models.PROTECT,
        related_name='departements',
        verbose_name='Faculté',
    )
    code = models.CharField(max_length=20, verbose_name='Sigle')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Département'
        verbose_name_plural = 'Départements'
        ordering = ['faculte_id', 'nom']
        constraints = [
            models.UniqueConstraint(
                fields=['faculte', 'code'],
                name='uniq_departement_code_par_faculte',
            ),
        ]

    def __str__(self):
        return f'{self.code} — {self.nom}'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class Filiere(models.Model):
    """Filière ou option, rattachée à un département."""
    departement = models.ForeignKey(
        Departement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='filieres',
        verbose_name='Département',
    )
    faculte = models.ForeignKey(
        Faculte,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='filieres',
        verbose_name='Faculté',
    )
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='filieres', verbose_name="Section", null=True, blank=True)
    code = models.CharField(max_length=20, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Filière"
        verbose_name_plural = "Filières"
        unique_together = [['section', 'code']]
        ordering = ['faculte_id', 'departement_id', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['departement', 'code'],
                condition=models.Q(departement__isnull=False),
                name='uniq_filiere_code_par_departement',
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        if self.departement_id:
            self.faculte_id = self.departement.faculte_id
        super().save(*args, **kwargs)


class AnneeAcademique(models.Model):
    """Année académique (ex: 2024-2025)"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    annee_debut = models.IntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)], verbose_name="Année début")
    annee_fin = models.IntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)], verbose_name="Année fin")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    active = models.BooleanField(default=False, verbose_name="Année active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Année académique"
        verbose_name_plural = "Années académiques"
        ordering = ['-annee_debut']

    def __str__(self):
        return f"{self.code} ({self.annee_debut}-{self.annee_fin})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.annee_fin != self.annee_debut + 1:
            raise ValidationError("L'année de fin doit être l'année de début + 1")

    @classmethod
    def get_active(cls):
        """Retourne l'année académique active (une seule à la fois)."""
        return cls.objects.filter(active=True).order_by('-annee_debut').first()

    @property
    def libelle_entete(self):
        """Libellé affiché dans l'en-tête applicatif."""
        return f'{self.annee_debut}-{self.annee_fin} (Année académique en cours)'

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.active:
                type(self).objects.filter(active=True).exclude(pk=self.pk).update(active=False)


class Promotion(models.Model):
    """Promotion (niveau) appartenant à une Filière (ex: Première, Deuxième, Troisième)"""
    filiere = models.ForeignKey(Filiere, on_delete=models.CASCADE, related_name='promotions', verbose_name="Filière", null=True, blank=True)
    code = models.CharField(max_length=20, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    ordre = models.IntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Ordre")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        unique_together = [['filiere', 'code']]
        ordering = ['filiere_id', 'ordre', 'code']

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class Local(models.Model):
    """Local (salle) pouvant accueillir une ou plusieurs classes"""
    code = models.CharField(max_length=30, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    capacite = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)], verbose_name="Capacité")
    active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Local"
        verbose_name_plural = "Locaux"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.nom}"


class Classe(models.Model):
    """Classe (ex: A, B, C) appartenant à une Promotion et affectée à un Local"""
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='classes', verbose_name="Promotion")
    code = models.CharField(max_length=10, verbose_name="Code")
    nom = models.CharField(max_length=200, blank=True, null=True, verbose_name="Nom")
    local = models.ForeignKey(
        Local,
        on_delete=models.PROTECT,
        related_name='classes',
        verbose_name="Local",
        null=True,
        blank=True,
        help_text="Salle, lorsqu'elle est déjà attribuée. La lettre de classe (A, B, …) suffit pour identifier l'étudiant.",
    )
    effectif_max = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)], verbose_name="Effectif maximum")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        unique_together = [['promotion', 'code']]
        ordering = ['promotion_id', 'code']

    def __str__(self):
        return f"{self.promotion.code}-{self.code}"

    def save(self, *args, **kwargs):
        if not self.nom:
            self.nom = f"Classe {self.code}"
        super().save(*args, **kwargs)


# ========== MODÈLES LMD ==========

class Semestre(models.Model):
    """Semestre LMD (catalogue : S1, S2, … — indépendant des promotions)"""
    numero = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Numéro",
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    credits_ects = models.IntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(60)], verbose_name="Crédits ECTS")
    date_debut = models.DateField(null=True, blank=True, verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Semestre"
        verbose_name_plural = "Semestres"
        ordering = ['numero']

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"S{self.numero}"
        if not self.nom:
            self.nom = f"Semestre {self.numero}"
        super().save(*args, **kwargs)


class UniteEnseignement(models.Model):
    """Unité d'Enseignement (UE) - composée de plusieurs EC"""
    semestre = models.ForeignKey(Semestre, on_delete=models.CASCADE, related_name='ues', verbose_name="Semestre")
    filiere = models.ForeignKey(
        Filiere,
        on_delete=models.CASCADE,
        related_name='ues',
        null=True,
        blank=True,
        verbose_name="Filière",
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    credits_ects = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Crédits ECTS"
    )
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Coefficient"
    )
    seuil_validation = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Seuil de validation (/20)"
    )
    compensation_autorisee = models.BooleanField(default=True, verbose_name="Compensation autorisée")
    capitalisable = models.BooleanField(default=True, verbose_name="Capitalisable")
    categorie = models.CharField(
        max_length=1,
        choices=[('A', 'Catégorie A'), ('B', 'Catégorie B')],
        default='A',
        verbose_name="Catégorie"
    )
    ordre = models.IntegerField(default=1, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unité d'Enseignement"
        verbose_name_plural = "Unités d'Enseignement"
        unique_together = [['semestre', 'filiere', 'code']]
        ordering = ['semestre', 'filiere', 'ordre', 'code']

    def __str__(self):
        return f"{self.code} - {self.nom} ({self.credits_ects} ECTS)"


class ElementConstitutif(models.Model):
    """Élément Constitutif (EC) - composant d'une UE"""
    ue = models.ForeignKey(UniteEnseignement, on_delete=models.CASCADE, related_name='ecs', verbose_name="UE")
    professeur = models.ForeignKey(
        'cards.Personnel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='elements_constitutifs',
        verbose_name="Professeur",
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    nom = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    credits_ects = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Crédits ECTS"
    )
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Coefficient"
    )
    volume_horaire = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)], verbose_name="Volume horaire (heures)")
    seuil_validation = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Seuil de validation (/20)"
    )
    note_eliminatoire = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('20.00'))],
        verbose_name="Note éliminatoire (/20)",
        help_text="Si renseignée, une note EC strictement inférieure bloque la validation et la compensation.",
    )
    compensation_autorisee = models.BooleanField(default=True, verbose_name="Compensation autorisée")
    capitalisable = models.BooleanField(default=True, verbose_name="Capitalisable")
    ordre = models.IntegerField(default=1, verbose_name="Ordre d'affichage")
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Élément Constitutif"
        verbose_name_plural = "Éléments Constitutifs"
        unique_together = [['ue', 'code']]
        ordering = ['ue', 'ordre', 'code']

    def __str__(self):
        return f"{self.code} - {self.nom} ({self.credits_ects} ECTS)"

    def note_est_eliminatoire(self, note) -> bool:
        """Vrai si la note finale est strictement inférieure au seuil éliminatoire de l'EC."""
        if note is None or self.note_eliminatoire is None:
            return False
        return note < self.note_eliminatoire
