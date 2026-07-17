"""
Modèles de configuration générale
"""
from django.db import models


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
