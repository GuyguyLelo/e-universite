import uuid

from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de la catégorie")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

class Position(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Poste / Fonction")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Poste / Fonction"
        verbose_name_plural = "Postes / Fonctions"

class Personnel(models.Model):
    SEX_CHOICES = (
        ("M", "Masculin"),
        ("F", "Féminin"),
    )
    MARITAL_STATUS_CHOICES = (
        ("single", "Célibataire"),
        ("married", "Marié(e)"),
        ("divorced", "Divorcé(e)"),
        ("widowed", "Veuf/Veuve"),
    )
    CONTRACT_TYPE_CHOICES = (
        ("permanent", "Permanent"),
        ("temporary", "Temporaire"),
        ("vacataire", "Vacataire"),
    )

    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True, verbose_name="Sexe")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Date de naissance")
    place_of_birth = models.CharField(max_length=150, blank=True, verbose_name="Lieu de naissance")
    nationality = models.CharField(max_length=100, blank=True, verbose_name="Nationalité")
    marital_status = models.CharField(
        max_length=20,
        choices=MARITAL_STATUS_CHOICES,
        blank=True,
        verbose_name="État civil",
    )
    current_address = models.TextField(blank=True, verbose_name="Adresse actuelle")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Adresse e-mail")

    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, verbose_name="Poste / Fonction")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, verbose_name="Catégorie")
    category_other = models.CharField(max_length=150, blank=True, verbose_name="Préciser la catégorie")
    function_quality = models.CharField(max_length=150, blank=True, verbose_name="Fonction / Qualité")
    grade = models.CharField(max_length=100, blank=True, verbose_name="Grade")
    education_level = models.CharField(max_length=100, verbose_name="Niveau d'études")
    assignment_service = models.CharField(max_length=150, blank=True, verbose_name="Service d'affectation")
    contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        blank=True,
        verbose_name="Type de contrat",
    )
    contract_reference = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Référence de l'acte d'engagement / contrat",
    )
    service_start_date = models.DateField(blank=True, null=True, verbose_name="Date de prise de service")

    identity_photo_physical = models.BooleanField(default=False, verbose_name="Photo d'identité récente format physique")
    identity_photo_digital = models.BooleanField(default=False, verbose_name="Photo d'identité récente format numérique")
    contract_copy_attached = models.BooleanField(default=False, verbose_name="Copie de l'acte d'engagement / contrat")
    other_pieces_attached = models.BooleanField(default=False, verbose_name="Autres pièces")
    other_pieces_details = models.TextField(blank=True, verbose_name="Préciser les autres pièces")

    matricule = models.CharField(max_length=50, blank=True, null=True, verbose_name="Matricule")
    photo = models.ImageField(upload_to='personnel/photos/', verbose_name="Photo de profil")
    contract_file = models.FileField(
        upload_to="personnel/contracts/",
        blank=True,
        null=True,
        verbose_name="Upload copie du contrat",
    )
    other_pieces_file = models.FileField(
        upload_to="personnel/other_pieces/",
        blank=True,
        null=True,
        verbose_name="Upload autres pièces",
    )

    engagement_confirmed = models.BooleanField(default=False, verbose_name="Confirmation de l'engagement")
    place_signed = models.CharField(max_length=100, default="Kinshasa", verbose_name="Fait à")
    signature_date = models.DateField(blank=True, null=True, verbose_name="Date de signature")
    name_signature = models.CharField(max_length=150, blank=True, verbose_name="Noms et signature")

    admin_received_by = models.CharField(max_length=150, blank=True, verbose_name="Dossier reçu par")
    admin_function = models.CharField(max_length=150, blank=True, verbose_name="Fonction")
    admin_received_date = models.DateField(blank=True, null=True, verbose_name="Date de réception")
    admin_observations = models.TextField(blank=True, verbose_name="Observations")
    admin_signature_stamp = models.CharField(max_length=200, blank=True, verbose_name="Signature et cachet")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.matricule}"

    class Meta:
        verbose_name = "Personnel"
        verbose_name_plural = "Personnels"

class Card(models.Model):
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, null=True, blank=True, related_name='cards', verbose_name="Personnel")
    issue_date = models.DateField(verbose_name="Date de délivrance")
    expiry_date = models.DateField(verbose_name="Date d'expiration")
    
    generated_card = models.ImageField(upload_to='cards/generated/', blank=True, null=True, verbose_name="Carte générée (Recto)")
    generated_card_back = models.ImageField(upload_to='cards/generated_back/', blank=True, null=True, verbose_name="Carte générée (Verso)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carte de {self.personnel.first_name} {self.personnel.last_name}"

    def delete(self, *args, **kwargs):
        # Supprime les fichiers images liés lors de la suppression de la carte
        if self.generated_card:
            self.generated_card.delete(save=False)
        if self.generated_card_back:
            self.generated_card_back.delete(save=False)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Carte PVC"
        verbose_name_plural = "Cartes PVC"
        ordering = ['-created_at']


class CardSettings(models.Model):
    """
    Configuration globale pour l'impression des cartes.
    Une seule ligne doit exister (singleton logique).
    """
    training_division_chief_title = models.CharField(
        max_length=150,
        default="Chef des divisions Formation",
        verbose_name="Titre affiché sous la photo"
    )
    training_division_chief_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Nom du Chef des divisions Formation"
    )
    training_division_chief_signature = models.ImageField(
        upload_to="cards/signatures/",
        blank=True,
        null=True,
        verbose_name="Signature (image) Chef divisions Formation"
    )

    digital_seal = models.ImageField(
    upload_to="cards/seals/",
    blank=True,
    null=True,
    verbose_name="Sceau numérique"
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Paramètres cartes (EFI)"
