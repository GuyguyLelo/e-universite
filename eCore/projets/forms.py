from django import forms

from academics.models import AnneeAcademique, Filiere, Semestre
from students.models import Student

from .models import ProjetAcademique


class ProjetAcademiqueForm(forms.ModelForm):
    class Meta:
        model = ProjetAcademique
        fields = [
            'titre',
            'resume',
            'mots_cles',
            'semestre',
            'filiere',
            'etudiants',
            'tuteur',
            'date_finalisation',
            'statut',
            'fichier',
            'lien_externe',
        ]
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du projet tutoré',
            }),
            'resume': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'mots_cles': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. intelligence artificielle, web, sécurité',
            }),
            'semestre': forms.Select(attrs={'class': 'form-control'}),
            'filiere': forms.Select(attrs={'class': 'form-control'}),
            'etudiants': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 8}),
            'tuteur': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du tuteur',
            }),
            'date_finalisation': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date'},
            ),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'fichier': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'lien_externe': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://…',
            }),
        }

    def __init__(self, *args, annee_active=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.annee_active = annee_active or AnneeAcademique.get_active()

        self.fields['semestre'].queryset = Semestre.objects.filter(active=True).order_by('numero')
        self.fields['semestre'].required = False
        self.fields['filiere'].queryset = Filiere.objects.filter(active=True).order_by('code')
        self.fields['filiere'].required = False

        etudiants_qs = Student.objects.filter(statut='actif').order_by('numero_etudiant')
        if self.annee_active:
            etudiants_qs = etudiants_qs.filter(
                inscriptions__annee_academique=self.annee_active,
            ).distinct()
        self.fields['etudiants'].queryset = etudiants_qs
        self.fields['etudiants'].required = False
        self.fields['etudiants'].label_from_instance = (
            lambda s: f"{s.numero_etudiant} — {s.identite_cotation}"
        )

    def clean(self):
        cleaned = super().clean()
        statut = cleaned.get('statut')
        date_fin = cleaned.get('date_finalisation')
        if statut == ProjetAcademique.STATUT_FINALISE and not date_fin:
            self.add_error(
                'date_finalisation',
                'La date de finalisation est obligatoire pour un projet finalisé.',
            )
        if not self.annee_active:
            raise forms.ValidationError(
                'Aucune année académique active. Définissez l\'année en cours.',
            )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.annee_academique = self.annee_active
        if commit:
            instance.save()
            self.save_m2m()
        return instance
