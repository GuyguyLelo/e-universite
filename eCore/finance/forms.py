from django import forms

from academics.models import AnneeAcademique, Semestre

from .models import MotifPaiement


class MotifPaiementForm(forms.ModelForm):
    class Meta:
        model = MotifPaiement
        fields = [
            'semestre',
            'contexte',
            'nom',
            'description',
            'montant',
            'devise',
            'ordre',
            'active',
        ]
        widgets = {
            'semestre': forms.Select(attrs={'class': 'form-control'}),
            'contexte': forms.Select(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Libellé (généré si vide)',
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'devise': forms.Select(attrs={'class': 'form-control'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '1'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, annee_active=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.annee_active = annee_active or AnneeAcademique.get_active()
        self.fields['semestre'].queryset = Semestre.objects.filter(active=True).order_by('numero')
        self.fields['semestre'].required = True
        self.fields['devise'].label = 'Devise du montant'
        self.fields['nom'].required = False
        self.fields['nom'].help_text = (
            'Laissé vide : libellé généré automatiquement (ex. Enrôlement session principale — S1).'
        )
        if self.instance.pk:
            self.fields['semestre'].disabled = True
            self.fields['contexte'].disabled = True
            self.fields['semestre'].help_text = 'Non modifiable — supprimez et recréez le motif pour changer de semestre.'
            self.fields['contexte'].help_text = 'Non modifiable — un seul motif par semestre et par type de session.'

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            cleaned['semestre'] = self.instance.semestre
            cleaned['contexte'] = self.instance.contexte

        semestre = cleaned.get('semestre')
        contexte = cleaned.get('contexte')

        if not semestre:
            self.add_error('semestre', 'Le semestre est obligatoire.')
        if not self.annee_active:
            raise forms.ValidationError(
                'Aucune année académique active. Définissez l\'année en cours dans la structure académique.',
            )

        if semestre and contexte and self.annee_active:
            conflit = MotifPaiement.objects.filter(
                annee_academique=self.annee_active,
                semestre=semestre,
                contexte=contexte,
            ).exclude(pk=self.instance.pk).first()
            if conflit:
                libelle = dict(MotifPaiement.CONTEXTE_CHOICES).get(contexte, contexte)
                raise forms.ValidationError(
                    f'Un motif « {libelle} » existe déjà pour le semestre '
                    f'{semestre.code} ({conflit.code}). Modifiez ce motif existant '
                    f'ou choisissez une autre combinaison.'
                )

        devise = cleaned.get('devise')
        montant = cleaned.get('montant')
        if devise == MotifPaiement.DEVISE_CDF and montant and montant % 1:
            self.add_error('montant', 'En CDF, saisissez un montant entier (sans centimes).')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not self.instance.pk:
            instance.annee_academique = self.annee_active
        if commit:
            instance.full_clean()
            instance.save()
        return instance
