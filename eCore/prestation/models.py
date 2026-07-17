from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from academics.models import AnneeAcademique, Classe, ElementConstitutif, Local, Semestre
from cards.models import Personnel


class EnveloppeBudgetaire(models.Model):
    MOIS_CHOICES = [
        (1, "Janvier"),
        (2, "Février"),
        (3, "Mars"),
        (4, "Avril"),
        (5, "Mai"),
        (6, "Juin"),
        (7, "Juillet"),
        (8, "Août"),
        (9, "Septembre"),
        (10, "Octobre"),
        (11, "Novembre"),
        (12, "Décembre"),
    ]

    annee = models.PositiveIntegerField(verbose_name="Année")
    mois = models.PositiveSmallIntegerField(
        choices=MOIS_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Mois",
    )
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        validators=[MinValueValidator(0)],
        verbose_name="Montant de l'enveloppe (CDF)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enveloppe budgétaire"
        verbose_name_plural = "Enveloppes budgétaires"
        ordering = ["-annee", "-mois"]
        constraints = [
            models.UniqueConstraint(fields=["annee", "mois"], name="unique_enveloppe_annee_mois"),
        ]

    def __str__(self):
        return f"{self.get_mois_display()} {self.annee} — {self.montant:,} CDF".replace(",", " ")

    def clean(self):
        if self.mois and (self.mois < 1 or self.mois > 12):
            raise ValidationError({"mois": "Le mois doit être compris entre 1 et 12."})


class PaieMensuelle(models.Model):
    enveloppe = models.OneToOneField(
        EnveloppeBudgetaire,
        on_delete=models.CASCADE,
        related_name="paie_validee",
        verbose_name="Enveloppe budgétaire",
    )
    montant_total_valide = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        verbose_name="Total validé (CDF)",
    )
    validee_le = models.DateTimeField(auto_now_add=True, verbose_name="Validée le")
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paies_mensuelles_validees",
        verbose_name="Validée par",
    )

    class Meta:
        verbose_name = "Clôture de paie mensuelle"
        verbose_name_plural = "Clôtures de paie mensuelle"
        ordering = ["-validee_le"]

    def __str__(self):
        return f"Paie {self.enveloppe}"


class BaremePrestation(models.Model):
    CATEGORIE_ENSEIGNEMENT = "enseignement"
    CATEGORIE_ACADEMIQUE = "academique"
    CATEGORIE_JURY = "jury"
    CATEGORIE_LOGISTIQUE = "logistique"

    CATEGORIE_CHOICES = [
        (CATEGORIE_ENSEIGNEMENT, "Enseignement (par période académique)"),
        (CATEGORIE_ACADEMIQUE, "Activités académiques (examens et autres)"),
        (CATEGORIE_JURY, "Jury et soutenance"),
        (CATEGORIE_LOGISTIQUE, "Avantages logistiques"),
    ]

    PERIODE_JOUR = "jour"
    PERIODE_HEURE = "heure"
    PERIODE_MOIS = "mois"
    PERIODE_MEMOIRE = "memoire"
    PERIODE_BAR = "bar"
    PERIODE_TFC = "tfc"
    PERIODE_LITRE = "litre"

    PERIODE_CHOICES = [
        (PERIODE_JOUR, "Jour"),
        (PERIODE_HEURE, "Heure"),
        (PERIODE_MOIS, "Mois"),
        (PERIODE_MEMOIRE, "Mémoire"),
        (PERIODE_BAR, "Bar"),
        (PERIODE_TFC, "TFC"),
        (PERIODE_LITRE, "Litre"),
    ]

    categorie = models.CharField(max_length=30, choices=CATEGORIE_CHOICES, verbose_name="Type prestation")
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES, verbose_name="Période")
    intitule = models.CharField(max_length=255, verbose_name="Intitulé")
    montant = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Montant (CDF)")
    active = models.BooleanField(default=True, verbose_name="Actif")
    ordre = models.PositiveIntegerField(default=1, verbose_name="Ordre")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Barème de prestation"
        verbose_name_plural = "Barèmes de prestation"
        ordering = ["categorie", "ordre", "intitule"]

    def __str__(self):
        return self.intitule


class PersonnelBaremeInitial(models.Model):
    personnel = models.ForeignKey(
        "cards.Personnel",
        on_delete=models.CASCADE,
        related_name="baremes_initiaux_liens",
        verbose_name="Personnel",
    )
    bareme = models.ForeignKey(
        BaremePrestation,
        on_delete=models.CASCADE,
        related_name="personnels_initiaux",
        verbose_name="Barème",
    )
    quantite = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Quantité",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Barème initial du personnel"
        verbose_name_plural = "Barèmes initiaux du personnel"
        ordering = ["personnel", "bareme__categorie", "bareme__ordre", "bareme__intitule"]
        constraints = [
            models.UniqueConstraint(
                fields=["personnel", "bareme"],
                name="unique_personnel_bareme_initial",
            ),
        ]

    def __str__(self):
        return f"{self.personnel} — {self.bareme}"

    @property
    def montant_unitaire(self):
        return self.bareme.montant if self.bareme_id else 0

    @property
    def montant_total(self):
        return self.montant_unitaire * self.quantite


class Prestation(models.Model):
    date_prestation = models.DateField(verbose_name="Date")
    personnel = models.ForeignKey(
        Personnel,
        on_delete=models.PROTECT,
        related_name="prestations",
        verbose_name="Personnel",
    )
    bareme = models.ForeignKey(
        BaremePrestation,
        on_delete=models.PROTECT,
        related_name="prestations",
        verbose_name="Barème",
    )
    categorie = models.CharField(
        max_length=30,
        choices=BaremePrestation.CATEGORIE_CHOICES,
        verbose_name="Type prestation",
    )
    montant = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Montant (CDF)")
    horaire = models.ForeignKey(
        "Horaire",
        on_delete=models.SET_NULL,
        related_name="prestations",
        verbose_name="Horaire",
        null=True,
        blank=True,
    )
    horaire_ligne = models.ForeignKey(
        "HoraireLigne",
        on_delete=models.SET_NULL,
        related_name="prestations",
        verbose_name="Ligne d'horaire",
        null=True,
        blank=True,
    )
    numero_fiche = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Numéro fiche",
    )
    jour = models.CharField(max_length=20, blank=True, verbose_name="Jour")
    heure_debut = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Heure début",
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prestation"
        verbose_name_plural = "Prestations"
        ordering = ["-date_prestation", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["date_prestation", "horaire_ligne"],
                condition=models.Q(horaire_ligne__isnull=False),
                name="unique_prestation_date_horaire_ligne",
            ),
        ]

    def __str__(self):
        return f"{self.date_prestation} - {self.personnel}"

    @property
    def section(self):
        if self.horaire and self.horaire.section:
            return self.horaire.section
        return None

    def save(self, *args, **kwargs):
        if self.bareme_id:
            self.categorie = self.bareme.categorie
            self.montant = self.bareme.montant
        super().save(*args, **kwargs)


class Horaire(models.Model):
    direction = models.CharField(
        max_length=255,
        default="DIRECTION DES SYSTEMES D'INFORMATION",
        verbose_name="Direction",
    )
    ecole = models.CharField(
        max_length=255,
        default="ECOLE INFORMATIQUE DES FINANCES",
        verbose_name="École",
    )
    systeme = models.CharField(
        max_length=255,
        default="SYSTÈME LMD/RESEAU",
        verbose_name="Système",
    )
    titre = models.CharField(
        max_length=255,
        default="Horaire des unités d'enseignement",
        verbose_name="Titre",
    )
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.PROTECT,
        related_name="horaires",
        verbose_name="Année académique",
    )
    semestre = models.ForeignKey(
        Semestre,
        on_delete=models.PROTECT,
        related_name="horaires",
        verbose_name="Semestre",
        null=True,
        blank=True,
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.PROTECT,
        related_name="horaires",
        verbose_name="Classe",
    )
    observation = models.TextField(blank=True, null=True, verbose_name="Observation")
    active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Horaire"
        verbose_name_plural = "Horaires"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.classe} - {self.annee_academique.code}"

    @property
    def section(self):
        return self.classe.promotion.filiere.section if self.classe and self.classe.promotion and self.classe.promotion.filiere else None

    @property
    def filiere(self):
        return self.classe.promotion.filiere if self.classe and self.classe.promotion else None

    @property
    def promotion(self):
        return self.classe.promotion if self.classe else None

    @property
    def local(self):
        return self.classe.local if self.classe else None

    @property
    def section_label(self):
        if self.section:
            return self.section.nom or self.section.code or "RESEAU"
        return "RESEAU"

    @property
    def systeme_affichage(self):
        return f"SYSTÈME LMD/{self.section_label}"

    @property
    def titre_document(self):
        classe_label = self.classe.promotion.code if self.classe and self.classe.promotion else self.classe.code
        semestre_label = self.semestre.nom.upper() if self.semestre else "SEMESTRE"
        return f"HORAIRE DES UNITÉS D'ENSEIGNEMENTS DU {semestre_label}: {classe_label}/{self.section_label}"

    @property
    def has_prestation_data(self):
        return self.lignes.exists()


class HoraireLigne(models.Model):
    JOUR_LUNDI = "lundi"
    JOUR_MARDI = "mardi"
    JOUR_MERCREDI = "mercredi"
    JOUR_JEUDI = "jeudi"
    JOUR_VENDREDI = "vendredi"
    JOUR_SAMEDI = "samedi"

    JOUR_CHOICES = [
        (JOUR_LUNDI, "Lundi"),
        (JOUR_MARDI, "Mardi"),
        (JOUR_MERCREDI, "Mercredi"),
        (JOUR_JEUDI, "Jeudi"),
        (JOUR_VENDREDI, "Vendredi"),
        (JOUR_SAMEDI, "Samedi"),
    ]

    JOUR_ORDER = {
        JOUR_LUNDI: 1,
        JOUR_MARDI: 2,
        JOUR_MERCREDI: 3,
        JOUR_JEUDI: 4,
        JOUR_VENDREDI: 5,
        JOUR_SAMEDI: 6,
    }

    horaire = models.ForeignKey(
        Horaire,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name="Horaire",
    )
    jour = models.CharField(max_length=20, choices=JOUR_CHOICES, verbose_name="Jour")
    heure_debut = models.TimeField(verbose_name="Heure début")
    heure_fin = models.TimeField(verbose_name="Heure fin")
    ue_code = models.CharField(max_length=50, blank=True, verbose_name="Code UE")
    element_constitutif = models.ForeignKey(
        ElementConstitutif,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horaire_lignes",
        verbose_name="Élément constitutif",
    )
    local = models.ForeignKey(
        Local,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horaire_lignes",
        verbose_name="Local",
    )
    professeur = models.ForeignKey(
        Personnel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="horaire_lignes",
        verbose_name="Professeur",
    )
    ordre = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Ordre")
    notes = models.CharField(max_length=255, blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ligne d'horaire"
        verbose_name_plural = "Lignes d'horaire"
        ordering = ["horaire", "jour", "heure_debut", "ordre"]

    def __str__(self):
        return f"{self.get_jour_display()} {self.heure_debut}-{self.heure_fin}"

    def clean(self):
        if self.heure_debut and self.heure_fin and self.heure_fin <= self.heure_debut:
            raise ValidationError({"heure_fin": "L'heure de fin doit être supérieure à l'heure de début."})
        if not self.ue_code and not self.element_constitutif:
            raise ValidationError("Veuillez renseigner le code UE ou sélectionner un élément constitutif.")
        if self.element_constitutif_id:
            ec = self.element_constitutif
            if ec.professeur_id:
                self.professeur = ec.professeur
            elif not self.professeur_id:
                self.professeur = None

    def save(self, *args, **kwargs):
        if self.element_constitutif_id:
            ec = self.element_constitutif
            if ec.professeur_id:
                self.professeur = ec.professeur
            if not self.ue_code and ec.code:
                self.ue_code = ec.code
        super().save(*args, **kwargs)

    @property
    def code_affichage(self):
        if self.element_constitutif:
            return self.element_constitutif.code
        return self.ue_code or "-"

    @property
    def intitule_affichage(self):
        if not self.element_constitutif_id:
            return ""
        ec = self.element_constitutif
        ue = ec.ue if ec.ue_id else None
        if ue and ec.nom and ue.nom and ec.nom.strip().lower() != ue.nom.strip().lower():
            return f"{ue.nom} — {ec.nom}"
        return ec.nom or (ue.nom if ue else "")

    @property
    def professeur_affichage(self):
        professeur = self.professeur
        if not professeur and self.element_constitutif_id:
            professeur = self.element_constitutif.professeur
        return professeur

    @property
    def titulaire_affichage(self):
        professeur = self.professeur_affichage
        if professeur:
            return f"{professeur.last_name} {professeur.first_name}".strip()
        if self.notes:
            prefix = "Enseignant:"
            if self.notes.startswith(prefix):
                return self.notes[len(prefix):].strip()
        return "-"

    @property
    def local_affichage(self):
        return str(self.local) if self.local else "-"
