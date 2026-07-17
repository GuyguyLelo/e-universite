from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class SessionFormation(models.Model):
    """Session de formation continue TIC (4 sessions / an, 4 mois chacune)."""

    annee = models.PositiveIntegerField(
        verbose_name='Année',
        help_text='Année civile de référence (ex. 2026)',
    )
    numero = models.PositiveSmallIntegerField(
        verbose_name='N° de session',
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text='De 1 à 4 (une session = 4 mois)',
    )
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin = models.DateField(verbose_name='Date de fin')
    active = models.BooleanField(default=True, verbose_name='Active')
    cloturee = models.BooleanField(default=False, verbose_name='Clôturée')
    date_cloture = models.DateTimeField(null=True, blank=True, verbose_name='Date de clôture')
    cloturee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions_fc_cloturees',
        verbose_name='Clôturée par',
    )
    observations_cloture = models.TextField(blank=True, verbose_name='Observations de clôture')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-annee', 'numero']
        unique_together = [('annee', 'numero')]
        verbose_name = 'Session de formation'
        verbose_name_plural = 'Sessions de formation'
        permissions = [
            ('cloturer_sessionformation', 'Peut clôturer une session de formation'),
        ]

    def __str__(self):
        return self.libelle or f'Session {self.numero}/{self.annee}'

    @property
    def en_cours(self):
        today = timezone.localdate()
        return (
            self.active
            and not self.cloturee
            and self.date_debut <= today <= self.date_fin
        )

    def peut_etre_cloturee(self):
        return not self.cloturee


class ModuleTIC(models.Model):
    """Module de formation aux TIC."""

    code = models.CharField(max_length=30, unique=True, verbose_name='Code')
    intitule = models.CharField(max_length=200, verbose_name='Intitulé')
    description = models.TextField(blank=True, verbose_name='Description')
    duree_heures = models.PositiveIntegerField(
        default=0,
        verbose_name='Durée (heures)',
    )
    active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'Module TIC'
        verbose_name_plural = 'Modules TIC'

    def __str__(self):
        return f'{self.code} — {self.intitule}'


class Formateur(models.Model):
    """Formateur dispensant un module."""

    nom = models.CharField(max_length=100, verbose_name='Nom')
    prenom = models.CharField(max_length=100, verbose_name='Prénom')
    telephone = models.CharField(max_length=40, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True, verbose_name='E-mail')
    specialite = models.CharField(max_length=150, blank=True, verbose_name='Spécialité')
    active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'prenom']
        verbose_name = 'Formateur'
        verbose_name_plural = 'Formateurs'

    def __str__(self):
        return f'{self.nom} {self.prenom}'.strip()

    @property
    def nom_complet(self):
        return f'{self.prenom} {self.nom}'.strip()


def seminariste_photo_path(instance, filename):
    folder = instance.matricule or instance.pk or 'nouveau'
    return f'formation_continue/seminaristes/{folder}/{filename}'


class Seminariste(models.Model):
    """Participant à une formation continue TIC."""

    TYPE_FONCTIONNAIRE = 'fonctionnaire'
    TYPE_INDEPENDANT = 'independant'
    TYPE_CHOICES = [
        (TYPE_FONCTIONNAIRE, 'Fonctionnaire (recommandé Admin. finances)'),
        (TYPE_INDEPENDANT, 'Indépendant'),
    ]

    type_participant = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='Type',
    )
    matricule = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Matricule / N° dossier',
    )
    nom = models.CharField(max_length=100, verbose_name='Nom')
    prenom = models.CharField(max_length=100, verbose_name='Prénom')
    photo = models.ImageField(
        upload_to=seminariste_photo_path,
        blank=True,
        null=True,
        verbose_name='Photo',
    )
    telephone = models.CharField(max_length=40, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True, verbose_name='E-mail')
    organisation = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Organisation / Service',
        help_text='Direction ou structure d’appartenance (fonctionnaires)',
    )
    recommande_par = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Recommandé par',
        help_text='Administration des finances ou autorité de tutelle',
    )
    observations = models.TextField(blank=True, verbose_name='Observations')
    active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom', 'prenom']
        verbose_name = 'Séminariste'
        verbose_name_plural = 'Séminaristes'

    def __str__(self):
        return f'{self.nom} {self.prenom}'.strip()

    @property
    def nom_complet(self):
        return f'{self.prenom} {self.nom}'.strip()


class OffreModule(models.Model):
    """Module dispensé dans une session par un formateur."""

    session = models.ForeignKey(
        SessionFormation,
        on_delete=models.CASCADE,
        related_name='offres',
        verbose_name='Session',
    )
    module = models.ForeignKey(
        ModuleTIC,
        on_delete=models.PROTECT,
        related_name='offres',
        verbose_name='Module',
    )
    formateur = models.ForeignKey(
        Formateur,
        on_delete=models.PROTECT,
        related_name='offres',
        verbose_name='Formateur',
    )
    date_debut = models.DateField(null=True, blank=True, verbose_name='Début du module')
    date_fin = models.DateField(null=True, blank=True, verbose_name='Fin du module')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session', 'module__code']
        unique_together = [('session', 'module')]
        verbose_name = 'Offre de module'
        verbose_name_plural = 'Offres de modules'

    def __str__(self):
        return f'{self.module} ({self.session}) — {self.formateur}'


class Inscription(models.Model):
    """Inscription d’un séminariste à une session."""

    STATUT_INSCRIT = 'inscrit'
    STATUT_EN_COURS = 'en_cours'
    STATUT_TERMINE = 'termine'
    STATUT_ABANDON = 'abandon'
    STATUT_CHOICES = [
        (STATUT_INSCRIT, 'Inscrit'),
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_TERMINE, 'Terminé'),
        (STATUT_ABANDON, 'Abandon'),
    ]

    seminariste = models.ForeignKey(
        Seminariste,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        verbose_name='Séminariste',
    )
    session = models.ForeignKey(
        SessionFormation,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        verbose_name='Session',
    )
    modules = models.ManyToManyField(
        OffreModule,
        blank=True,
        related_name='inscriptions',
        verbose_name='Modules suivis',
    )
    date_inscription = models.DateField(
        default=timezone.localdate,
        verbose_name='Date d’inscription',
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_INSCRIT,
        verbose_name='Statut',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_inscription', 'seminariste__nom']
        unique_together = [('seminariste', 'session')]
        verbose_name = 'Inscription'
        verbose_name_plural = 'Inscriptions'

    def __str__(self):
        return f'{self.seminariste} — {self.session}'


class Presence(models.Model):
    """Présence d’un séminariste à une séance de module."""

    STATUT_PRESENT = 'present'
    STATUT_ABSENT = 'absent'
    STATUT_RETARD = 'retard'
    STATUT_EXCUSE = 'excuse'
    STATUT_CHOICES = [
        (STATUT_PRESENT, 'Présent'),
        (STATUT_ABSENT, 'Absent'),
        (STATUT_RETARD, 'Retard'),
        (STATUT_EXCUSE, 'Excusé'),
    ]

    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='presences',
        verbose_name='Inscription',
    )
    offre_module = models.ForeignKey(
        OffreModule,
        on_delete=models.CASCADE,
        related_name='presences',
        verbose_name='Module',
    )
    date_seance = models.DateField(verbose_name='Date de séance')
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_PRESENT,
        verbose_name='Statut',
    )
    remarque = models.CharField(max_length=255, blank=True, verbose_name='Remarque')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_seance', 'inscription__seminariste__nom']
        unique_together = [('inscription', 'offre_module', 'date_seance')]
        verbose_name = 'Présence'
        verbose_name_plural = 'Présences'

    def __str__(self):
        return f'{self.inscription.seminariste} — {self.date_seance} ({self.get_statut_display()})'


def brevet_upload_path(instance, filename):
    return f'formation_continue/brevets/{instance.session.annee}/{filename}'


class Brevet(models.Model):
    """Brevet délivré à l’issue d’une formation."""

    seminariste = models.ForeignKey(
        Seminariste,
        on_delete=models.CASCADE,
        related_name='brevets',
        verbose_name='Séminariste',
    )
    session = models.ForeignKey(
        SessionFormation,
        on_delete=models.PROTECT,
        related_name='brevets',
        verbose_name='Session',
    )
    numero = models.CharField(max_length=60, unique=True, verbose_name='N° de brevet')
    date_delivrance = models.DateField(
        default=timezone.localdate,
        verbose_name='Date de délivrance',
    )
    modules_valides = models.ManyToManyField(
        ModuleTIC,
        blank=True,
        related_name='brevets',
        verbose_name='Modules validés',
    )
    fichier = models.FileField(
        upload_to=brevet_upload_path,
        blank=True,
        null=True,
        verbose_name='Fichier PDF',
    )
    observations = models.TextField(blank=True, verbose_name='Observations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_delivrance', 'numero']
        unique_together = [('seminariste', 'session')]
        verbose_name = 'Brevet'
        verbose_name_plural = 'Brevets'

    def __str__(self):
        return f'{self.numero} — {self.seminariste}'

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.session_id and not self.session.cloturee:
            raise ValidationError({
                'session': 'Les brevets ne sont disponibles qu’après clôture de la session.',
            })
