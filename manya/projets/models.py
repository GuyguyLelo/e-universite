import os

from django.db import models

from academics.models import AnneeAcademique, ElementConstitutif, Filiere, Semestre
from students.models import Student


def projet_fichier_path(instance, filename):
    return f'projets/{instance.annee_academique.code}/{instance.pk or "new"}/{filename}'


class ProjetAcademique(models.Model):
    """Projet tutoré académique (consultation des travaux finalisés)."""

    STATUT_BROUILLON = 'brouillon'
    STATUT_FINALISE = 'finalise'
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_FINALISE, 'Finalisé'),
    ]

    titre = models.CharField(max_length=300, verbose_name='Titre du projet')
    resume = models.TextField(blank=True, verbose_name='Résumé')
    mots_cles = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Mots-clés',
        help_text='Séparés par des virgules',
    )
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='projets_academiques',
        verbose_name='Année académique',
    )
    semestre = models.ForeignKey(
        Semestre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projets_academiques',
        verbose_name='Semestre',
    )
    filiere = models.ForeignKey(
        Filiere,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projets_academiques',
        verbose_name='Filière',
    )
    element_constitutif = models.ForeignKey(
        ElementConstitutif,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projets_academiques',
        verbose_name='Élément constitutif',
    )
    etudiants = models.ManyToManyField(
        Student,
        blank=True,
        related_name='projets_academiques',
        verbose_name='Étudiants',
    )
    tuteur = models.CharField(max_length=200, blank=True, verbose_name='Tuteur')
    date_finalisation = models.DateField(null=True, blank=True, verbose_name='Date de finalisation')
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_BROUILLON,
        verbose_name='Statut',
    )
    fichier = models.FileField(
        upload_to=projet_fichier_path,
        blank=True,
        null=True,
        verbose_name='Document (PDF, etc.)',
    )
    lien_externe = models.URLField(blank=True, verbose_name='Lien externe')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Projet académique'
        verbose_name_plural = 'Projets académiques'
        ordering = ['-date_finalisation', '-created_at']
        permissions = [
            ('consulter_projets_finalises', 'Consulter les projets académiques finalisés'),
        ]

    def __str__(self):
        return self.titre

    @property
    def est_finalise(self):
        return self.statut == self.STATUT_FINALISE

    @property
    def etudiants_libelle(self):
        noms = [e.identite_cotation for e in self.etudiants.all()[:5]]
        extra = self.etudiants.count() - len(noms)
        if extra > 0:
            noms.append(f'+{extra}')
        return ', '.join(noms) if noms else '—'

    @property
    def fichier_nom(self):
        if self.fichier:
            return os.path.basename(self.fichier.name)
        return ''
