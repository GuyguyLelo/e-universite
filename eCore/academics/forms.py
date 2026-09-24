"""
Formulaires pour l'application academics
"""
from django import forms

from cards.models import Personnel

from .models import (
    Section, Faculte, Departement, Filiere, Promotion, Classe, Local,
    AnneeAcademique, Semestre,
    UniteEnseignement, ElementConstitutif
)


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['etablissement', 'code', 'nom', 'description', 'active']
        widgets = {
            'etablissement': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code de la section (ex: L, M)'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la section (ex: Licence, Master)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FaculteForm(forms.ModelForm):
    class Meta:
        model = Faculte
        fields = ['etablissement', 'code', 'nom', 'description', 'active']
        widgets = {
            'etablissement': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DROIT'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Faculté de Droit'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DepartementForm(forms.ModelForm):
    class Meta:
        model = Departement
        fields = ['faculte', 'code', 'nom', 'description', 'active']
        widgets = {
            'faculte': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DPJ'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Droit privé et judiciaire'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FiliereForm(forms.ModelForm):
    class Meta:
        model = Filiere
        fields = ['faculte', 'departement', 'section', 'code', 'nom', 'description', 'active']
        widgets = {
            'faculte': forms.Select(attrs={'class': 'form-control'}),
            'departement': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code de la filière'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la filière'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = ['filiere', 'code', 'nom', 'ordre', 'active']
        widgets = {
            'filiere': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: P1, P2, P3'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Première, Deuxième, Troisième'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class LocalForm(forms.ModelForm):
    class Meta:
        model = Local
        fields = ['code', 'nom', 'capacite', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: L14'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Local 14'}),
            'capacite': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Ex. 40'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ClasseForm(forms.ModelForm):
    class Meta:
        model = Classe
        fields = ['promotion', 'code', 'nom', 'local', 'effectif_max', 'active']
        widgets = {
            'promotion': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: A, B, C'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom (optionnel)'}),
            'local': forms.Select(attrs={'class': 'form-control'}),
            'effectif_max': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AnneeAcademiqueForm(forms.ModelForm):
    class Meta:
        model = AnneeAcademique
        fields = ['code', 'annee_debut', 'annee_fin', 'date_debut', 'date_fin', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2024-2025'}),
            'annee_debut': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
            'annee_fin': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['active'].help_text = (
            "Une seule année peut être active. L'activation désactive automatiquement les autres."
        )


class SemestreForm(forms.ModelForm):
    class Meta:
        model = Semestre
        fields = ['numero', 'code', 'nom', 'credits_ects', 'date_debut', 'date_fin', 'active']
        widgets = {
            'numero': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code automatique si vide'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom automatique si vide'}),
            'credits_ects': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60, 'value': 30}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UniteEnseignementForm(forms.ModelForm):
    class Meta:
        model = UniteEnseignement
        fields = [
            'semestre', 'filiere', 'code', 'nom', 'description', 'credits_ects',
            'coefficient', 'seuil_validation', 'compensation_autorisee',
            'capitalisable', 'categorie', 'ordre', 'active'
        ]
        widgets = {
            'semestre': forms.Select(attrs={'class': 'form-control'}),
            'filiere': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code UE'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de l\'UE'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'credits_ects': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0.5}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'value': 1.0}),
            'seuil_validation': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0, 'max': 20, 'value': 10.0}),
            'compensation_autorisee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capitalisable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ElementConstitutifForm(forms.ModelForm):
    class Meta:
        model = ElementConstitutif
        fields = [
            'ue', 'code', 'nom', 'professeur', 'description', 'credits_ects',
            'coefficient', 'volume_horaire', 'seuil_validation', 'note_eliminatoire',
            'compensation_autorisee', 'capitalisable', 'ordre', 'active'
        ]
        widgets = {
            'ue': forms.Select(attrs={'class': 'form-control'}),
            'professeur': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code EC'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de l\'EC'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'credits_ects': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0.5}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'value': 1.0}),
            'volume_horaire': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'seuil_validation': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0, 'max': 20, 'value': 10.0}),
            'note_eliminatoire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0, 'max': 20, 'placeholder': 'Ex. 7.0'}),
            'compensation_autorisee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capitalisable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["professeur"].queryset = Personnel.objects.select_related(
            "position", "category"
        ).order_by("last_name", "first_name")
        self.fields["professeur"].required = False


class UEListFilterForm(forms.Form):
    semestre = forms.ModelChoiceField(
        queryset=Semestre.objects.filter(active=True).order_by('numero'),
        required=False,
        label="Semestre",
        empty_label="Tous les semestres",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label="Filière",
        empty_label="Toutes les filières",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['semestre'].label_from_instance = lambda obj: (
            f"{obj.code} — {obj.nom} ({UniteEnseignement.objects.filter(semestre=obj).count()})"
        )
        self.fields['filiere'].label_from_instance = lambda obj: (
            f"{obj.nom} ({UniteEnseignement.objects.filter(filiere=obj).count()})"
        )
