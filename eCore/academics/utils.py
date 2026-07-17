"""Utilitaires académiques partagés."""

from django import forms

from .models import AnneeAcademique

NO_ACTIVE_ANNEE_ERROR = (
    "Aucune année académique active. "
    "Définissez-en une dans Structure → Années académiques."
)


def get_active_annee_required():
    """Retourne l'année académique active ou None."""
    return AnneeAcademique.get_active()


class ActiveAnneeModelFormMixin:
    """Retire le champ année du formulaire et l'assigne automatiquement à la création."""

    active_annee_field = 'annee_academique'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.active_annee_field in self.fields:
            del self.fields[self.active_annee_field]

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not AnneeAcademique.get_active():
            raise forms.ValidationError(NO_ACTIVE_ANNEE_ERROR)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk and not instance.annee_academique_id:
            instance.annee_academique = AnneeAcademique.get_active()
        if commit:
            instance.save()
            self.save_m2m()
        return instance
