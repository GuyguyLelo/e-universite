"""
Modèles de configuration générale.

Le registre des établissements couvre l'enseignement supérieur de la RDC
(public et privé). L'UNIKIN est l'établissement de la phase pilote.
"""
from django.core.exceptions import ValidationError
from django.db import models


PROVINCES_RDC = [
    ('Kinshasa', 'Kinshasa'),
    ('Kongo-Central', 'Kongo-Central'),
    ('Kwango', 'Kwango'),
    ('Kwilu', 'Kwilu'),
    ('Mai-Ndombe', 'Mai-Ndombe'),
    ('Équateur', 'Équateur'),
    ('Mongala', 'Mongala'),
    ('Nord-Ubangi', 'Nord-Ubangi'),
    ('Sud-Ubangi', 'Sud-Ubangi'),
    ('Tshuapa', 'Tshuapa'),
    ('Tshopo', 'Tshopo'),
    ('Bas-Uele', 'Bas-Uele'),
    ('Haut-Uele', 'Haut-Uele'),
    ('Ituri', 'Ituri'),
    ('Nord-Kivu', 'Nord-Kivu'),
    ('Sud-Kivu', 'Sud-Kivu'),
    ('Maniema', 'Maniema'),
    ('Haut-Katanga', 'Haut-Katanga'),
    ('Haut-Lomami', 'Haut-Lomami'),
    ('Lualaba', 'Lualaba'),
    ('Tanganyika', 'Tanganyika'),
    ('Lomami', 'Lomami'),
    ('Kasaï', 'Kasaï'),
    ('Kasaï-Central', 'Kasaï-Central'),
    ('Kasaï-Oriental', 'Kasaï-Oriental'),
    ('Sankuru', 'Sankuru'),
]

TUTELLE_ESU = "Ministère de l'Enseignement Supérieur et Universitaire"


class Etablissement(models.Model):
    """Établissement d'enseignement supérieur, public ou privé, agréé en RDC."""

    STATUT_PUBLIC = 'public'
    STATUT_PRIVE = 'prive'
    STATUT_CHOICES = [
        (STATUT_PUBLIC, 'Public'),
        (STATUT_PRIVE, 'Privé'),
    ]

    CATEGORIE_UNIVERSITE = 'universite'
    CATEGORIE_INSTITUT = 'institut_superieur'
    CATEGORIE_ISP = 'isp'
    CATEGORIE_IST = 'ist'
    CATEGORIE_ISTM = 'istm'
    CATEGORIE_ECOLE = 'ecole_superieure'
    CATEGORIE_GRANDE_ECOLE = 'grande_ecole'
    CATEGORIE_CHOICES = [
        (CATEGORIE_UNIVERSITE, 'Université'),
        (CATEGORIE_INSTITUT, 'Institut supérieur'),
        (CATEGORIE_ISP, 'Institut supérieur pédagogique'),
        (CATEGORIE_IST, 'Institut supérieur technique'),
        (CATEGORIE_ISTM, 'Institut supérieur des techniques médicales'),
        (CATEGORIE_ECOLE, 'École supérieure'),
        (CATEGORIE_GRANDE_ECOLE, 'Grande école'),
    ]

    PHASE_PILOTE = 'pilote'
    PHASE_EXTENSION = 'extension'
    PHASE_GENERALISATION = 'generalisation'
    PHASE_CHOICES = [
        (PHASE_PILOTE, 'Pilote'),
        (PHASE_EXTENSION, 'Extension'),
        (PHASE_GENERALISATION, 'Généralisation'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name='Sigle')
    nom = models.CharField(max_length=255, verbose_name='Nom officiel')
    statut_juridique = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        verbose_name='Statut juridique',
    )
    categorie = models.CharField(
        max_length=30,
        choices=CATEGORIE_CHOICES,
        verbose_name='Catégorie',
    )
    province = models.CharField(max_length=40, choices=PROVINCES_RDC, verbose_name='Province')
    ville = models.CharField(max_length=100, verbose_name='Ville')
    adresse = models.TextField(blank=True, verbose_name='Adresse')
    telephone = models.CharField(max_length=50, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True, verbose_name='Email')
    site_web = models.URLField(blank=True, verbose_name='Site web')
    tutelle = models.CharField(
        max_length=200,
        default=TUTELLE_ESU,
        verbose_name='Tutelle',
    )
    numero_agrement = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Numéro d'agrément",
        help_text='Obligatoire pour un établissement privé.',
    )
    date_agrement = models.DateField(null=True, blank=True, verbose_name="Date d'agrément")
    promoteur = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Promoteur',
        help_text='Personne morale ou physique, pour un établissement privé.',
    )
    phase = models.CharField(
        max_length=20,
        choices=PHASE_CHOICES,
        default=PHASE_EXTENSION,
        verbose_name='Phase de déploiement',
    )
    logo = models.ImageField(
        upload_to='etablissements/logos/',
        blank=True,
        null=True,
        verbose_name='Logo',
        help_text='Image PNG, JPEG ou WebP, 2 Mo au plus.',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Établissement'
        verbose_name_plural = 'Établissements'
        ordering = ['nom']

    def __str__(self):
        return f'{self.code} — {self.nom}'

    def clean(self):
        if self.statut_juridique == self.STATUT_PRIVE and not (self.numero_agrement or '').strip():
            raise ValidationError({
                'numero_agrement': "L'agrément du ministère est obligatoire pour un établissement privé.",
            })

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @classmethod
    def get_pilote(cls):
        return cls.objects.filter(phase=cls.PHASE_PILOTE, actif=True).order_by('code').first()


class ConfigurationGenerale(models.Model):
    """Configuration générale de l'application"""
    nom_universite = models.CharField(max_length=200, default="Université", verbose_name="Nom de l'université")
    logo = models.ImageField(upload_to='config/', blank=True, null=True, verbose_name="Logo")
    adresse = models.TextField(blank=True, null=True, verbose_name="Adresse")
    telephone = models.CharField(max_length=50, blank=True, null=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    site_web = models.URLField(blank=True, null=True, verbose_name="Site web")
    
    class Meta:
        verbose_name = "Configuration générale"
        verbose_name_plural = "Configurations générales"

    def __str__(self):
        return f"Configuration - {self.nom_universite}"

    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'une seule configuration
        self.pk = 1
        super().save(*args, **kwargs)
