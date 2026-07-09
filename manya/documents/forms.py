"""
Formulaires pour le module documents (attestations).
"""
from django import forms

from academics.models import AnneeAcademique, Filiere, Promotion, Classe
from students.models import Inscription
from .models import Attestation, TypeAttestation


class AttestationForm(forms.ModelForm):
    class Meta:
        model = Attestation
        fields = [
            'type_attestation',
            'inscription',
            'date_delivrance',
            'lieu_delivrance',
            'objet',
            'notes',
        ]
        widgets = {
            'type_attestation': forms.Select(attrs={'class': 'form-control'}),
            'inscription': forms.Select(attrs={'class': 'form-control'}),
            'date_delivrance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_delivrance': forms.TextInput(attrs={'class': 'form-control'}),
            'objet': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, annee=None, **kwargs):
        super().__init__(*args, **kwargs)
        annee = annee or AnneeAcademique.get_active()
        self.fields['type_attestation'].queryset = (
            TypeAttestation.objects.filter(active=True).order_by('ordre', 'nom')
        )
        inscriptions = (
            Inscription.objects.filter(annee_academique=annee, classe__isnull=False)
            .eligibles_listes()
            .select_related(
                'etudiant',
                'classe',
                'classe__promotion',
                'classe__promotion__filiere',
                'annee_academique',
            )
            .order_by('classe__promotion__filiere__code', 'classe__code', 'etudiant__nom')
        )
        self.fields['inscription'].queryset = inscriptions
        self.fields['inscription'].label_from_instance = (
            lambda obj: (
                f'{obj.etudiant.numero_etudiant} — {obj.etudiant.nom} {obj.etudiant.prenom} '
                f'({obj.classe.promotion.code} / {obj.classe.code})'
            )
        )
        self.fields['objet'].required = False
        self.fields['notes'].required = False


class AttestationListFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Rechercher',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'N°, étudiant, attestation…',
        }),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label='Filière',
        empty_label='Toutes les filières',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    promotion = forms.ModelChoiceField(
        queryset=Promotion.objects.none(),
        required=False,
        label='Promotion',
        empty_label='Toutes les promotions',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label='Classe',
        empty_label='Toutes les classes',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    type_attestation = forms.ModelChoiceField(
        queryset=TypeAttestation.objects.filter(active=True).order_by('ordre', 'nom'),
        required=False,
        label="Type",
        empty_label='Tous les types',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    def __init__(self, *args, annee=None, **kwargs):
        super().__init__(*args, **kwargs)
        annee = annee or AnneeAcademique.get_active()
        filiere = None
        promotion = None
        if self.data.get('filiere'):
            try:
                filiere = Filiere.objects.filter(pk=int(self.data['filiere'])).first()
            except (TypeError, ValueError):
                filiere = None
        if self.data.get('promotion'):
            try:
                promotion = Promotion.objects.filter(pk=int(self.data['promotion'])).first()
            except (TypeError, ValueError):
                promotion = None

        promotion_qs = Promotion.objects.filter(active=True).select_related('filiere')
        if filiere:
            promotion_qs = promotion_qs.filter(filiere=filiere)
        if annee:
            promotion_qs = promotion_qs.filter(
                classes__inscriptions__annee_academique=annee,
            ).distinct()
        self.fields['promotion'].queryset = promotion_qs.order_by('filiere__code', 'ordre', 'code')

        classe_qs = (
            Classe.objects.filter(active=True)
            .select_related('promotion', 'promotion__filiere')
            .order_by('promotion__filiere__code', 'promotion__ordre', 'code')
        )
        if annee:
            classe_qs = classe_qs.filter(
                inscriptions__annee_academique=annee,
            ).distinct()
        if filiere:
            classe_qs = classe_qs.filter(promotion__filiere=filiere)
        if promotion:
            classe_qs = classe_qs.filter(promotion=promotion)
        self.fields['classe'].queryset = classe_qs

        self.fields['filiere'].label_from_instance = lambda obj: obj.code
        self.fields['promotion'].label_from_instance = lambda obj: f'{obj.code} — {obj.nom}'
        self.fields['classe'].label_from_instance = (
            lambda obj: f'{obj.promotion.code} — {obj.code}'
        )
