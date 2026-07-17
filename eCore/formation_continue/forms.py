from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Brevet,
    Formateur,
    Inscription,
    ModuleTIC,
    OffreModule,
    Presence,
    Seminariste,
    SessionFormation,
)


class SessionFormationForm(forms.ModelForm):
    class Meta:
        model = SessionFormation
        fields = ['annee', 'numero', 'libelle', 'date_debut', 'date_fin', 'active']
        widgets = {
            'annee': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
            'numero': forms.Select(
                choices=[(i, f'Session {i}') for i in range(1, 5)],
                attrs={'class': 'form-control'},
            ),
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        if debut and fin and fin < debut:
            raise ValidationError('La date de fin doit être postérieure à la date de début.')
        return cleaned


class ModuleTICForm(forms.ModelForm):
    class Meta:
        model = ModuleTIC
        fields = ['code', 'intitule', 'description', 'duree_heures', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'intitule': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'duree_heures': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FormateurForm(forms.ModelForm):
    class Meta:
        model = Formateur
        fields = ['nom', 'prenom', 'telephone', 'email', 'specialite', 'active']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'specialite': forms.TextInput(attrs={'class': 'form-control'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SeminaristeForm(forms.ModelForm):
    class Meta:
        model = Seminariste
        fields = [
            'type_participant',
            'matricule',
            'nom',
            'prenom',
            'photo',
            'telephone',
            'email',
            'organisation',
            'recommande_par',
            'observations',
            'active',
        ]
        widgets = {
            'type_participant': forms.Select(attrs={'class': 'form-control'}),
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'organisation': forms.TextInput(attrs={'class': 'form-control'}),
            'recommande_par': forms.TextInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OffreModuleForm(forms.ModelForm):
    class Meta:
        model = OffreModule
        fields = ['session', 'module', 'formateur', 'date_debut', 'date_fin']
        widgets = {
            'session': forms.Select(attrs={'class': 'form-control'}),
            'module': forms.Select(attrs={'class': 'form-control'}),
            'formateur': forms.Select(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['session'].queryset = SessionFormation.objects.filter(
            active=True, cloturee=False
        )
        self.fields['module'].queryset = ModuleTIC.objects.filter(active=True)
        self.fields['formateur'].queryset = Formateur.objects.filter(active=True)


class InscriptionForm(forms.ModelForm):
    class Meta:
        model = Inscription
        fields = ['seminariste', 'session', 'modules', 'date_inscription', 'statut']
        widgets = {
            'seminariste': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'modules': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 6}),
            'date_inscription': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seminariste'].queryset = Seminariste.objects.filter(active=True)
        self.fields['session'].queryset = SessionFormation.objects.filter(
            active=True, cloturee=False
        )
        session_id = None
        if self.data.get('session'):
            session_id = self.data.get('session')
        elif self.instance and self.instance.pk:
            session_id = self.instance.session_id
        qs = OffreModule.objects.select_related('module', 'formateur')
        if session_id:
            qs = qs.filter(session_id=session_id)
        self.fields['modules'].queryset = qs
        self.fields['modules'].required = False


class PresenceForm(forms.ModelForm):
    class Meta:
        model = Presence
        fields = ['inscription', 'offre_module', 'date_seance', 'statut', 'remarque']
        widgets = {
            'inscription': forms.Select(attrs={'class': 'form-control'}),
            'offre_module': forms.Select(attrs={'class': 'form-control'}),
            'date_seance': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'remarque': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inscription'].queryset = (
            Inscription.objects.select_related('seminariste', 'session')
            .exclude(statut=Inscription.STATUT_ABANDON)
        )
        self.fields['offre_module'].queryset = OffreModule.objects.select_related(
            'module', 'session', 'formateur'
        )


class BrevetForm(forms.ModelForm):
    class Meta:
        model = Brevet
        fields = [
            'seminariste',
            'session',
            'numero',
            'date_delivrance',
            'modules_valides',
            'observations',
        ]
        widgets = {
            'seminariste': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
            'date_delivrance': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'modules_valides': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 6}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seminariste'].queryset = Seminariste.objects.filter(active=True)
        sessions_qs = SessionFormation.objects.filter(cloturee=True).order_by('-annee', 'numero')
        if self.instance and self.instance.pk and self.instance.session_id:
            sessions_qs = (
                SessionFormation.objects.filter(Q(pk=self.instance.session_id) | Q(cloturee=True))
                .distinct()
                .order_by('-annee', 'numero')
            )
        self.fields['session'].queryset = sessions_qs
        self.fields['session'].help_text = 'Seules les sessions clôturées sont éligibles aux brevets.'
        self.fields['modules_valides'].queryset = ModuleTIC.objects.filter(active=True)
        self.fields['modules_valides'].required = False
        self.fields['observations'].help_text = (
            'Laisser vide pour le texte standard du brevet. Un texte personnalisé remplace le corps du PDF.'
        )

    def clean_session(self):
        session = self.cleaned_data.get('session')
        if session and not session.cloturee:
            raise ValidationError(
                'Les brevets ne sont disponibles qu’après clôture de la session.'
            )
        return session
