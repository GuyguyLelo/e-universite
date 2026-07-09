"""
Formulaires pour l'application deliberations
"""
from django import forms
from django.contrib.auth.models import User
from .models import ParametresLMD, Deliberation, DecisionJury
from deliberations.jury_bureau import est_promotion_master1_csi_rx, valeurs_jury_m1_defaut
from academics.models import Promotion, AnneeAcademique, Semestre, Filiere, Classe
from evaluations.models import Session
from students.models import Student, Inscription


class ParametresLMDForm(forms.ModelForm):
    class Meta:
        model = ParametresLMD
        fields = [
            'promotion', 'seuil_validation', 'compensation_intra_ue',
            'compensation_intra_semestre', 'compensation_annuelle',
            'capitalisation_ue', 'capitalisation_ec', 'passage_avec_dettes',
            'seuil_credits_minimum'
        ]
        widgets = {
            'promotion': forms.Select(attrs={'class': 'form-control'}),
            'seuil_validation': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0, 'max': 20, 'value': 10.0}),
            'compensation_intra_ue': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compensation_intra_semestre': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compensation_annuelle': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capitalisation_ue': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capitalisation_ec': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'passage_avec_dettes': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'seuil_credits_minimum': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 30}),
        }


class DeliberationForm(forms.ModelForm):
    class Meta:
        model = Deliberation
        fields = [
            'type_deliberation', 'session', 'promotion',
            'annee_academique', 'annee_academique_m1', 'semestre1', 'semestre2',
            'date_deliberation', 'president_jury', 'president_jury_nom', 'secretaire_jury_nom',
            'membres_jury', 'membres_jury_noms', 'statut', 'notes',
        ]
        widgets = {
            'type_deliberation': forms.Select(attrs={'class': 'form-control', 'id': 'id_type_deliberation'}),
            'session': forms.Select(attrs={'class': 'form-control', 'id': 'id_session'}),
            'promotion': forms.Select(attrs={'class': 'form-control'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control', 'id': 'id_annee_academique'}),
            'annee_academique_m1': forms.Select(attrs={'class': 'form-control', 'id': 'id_annee_academique_m1'}),
            'semestre1': forms.Select(attrs={'class': 'form-control', 'id': 'id_semestre1'}),
            'semestre2': forms.Select(attrs={'class': 'form-control', 'id': 'id_semestre2'}),
            'date_deliberation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'president_jury': forms.Select(attrs={'class': 'form-control'}),
            'president_jury_nom': forms.TextInput(attrs={'class': 'form-control'}),
            'secretaire_jury_nom': forms.TextInput(attrs={'class': 'form-control'}),
            'membres_jury': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
            'membres_jury_noms': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['session'].required = False
        self.fields['annee_academique'].required = False
        self.fields['annee_academique_m1'].required = False
        self.fields['semestre1'].required = False
        self.fields['semestre2'].required = False
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.order_by('-annee_debut')
        self.fields['annee_academique_m1'].queryset = AnneeAcademique.objects.order_by('-annee_debut')
        self.fields['annee_academique'].label = 'Année académique'
        self.fields['annee_academique_m1'].label = 'Année académique Master 1'
        self.fields['semestre1'].queryset = Semestre.objects.filter(active=True).order_by('numero')
        self.fields['semestre2'].queryset = Semestre.objects.filter(active=True).order_by('numero')
        self.fields['session'].queryset = (
            Session.pour_annee(AnneeAcademique.get_active())
            .filter(active=True)
            .select_related('semestre', 'annee_academique')
            .order_by('semestre__numero', 'numero')
        )
        type_initial = None
        if self.data:
            type_initial = self.data.get('type_deliberation')
        elif self.instance.pk:
            type_initial = self.instance.type_deliberation
        if type_initial == Deliberation.TYPE_CYCLE_MASTER:
            self.fields['annee_academique'].label = 'Année académique Master 2'

        if not self.instance.pk:
            defaults = valeurs_jury_m1_defaut()
            self.fields['president_jury_nom'].initial = defaults['president']
            self.fields['secretaire_jury_nom'].initial = defaults['secretaire']
            self.fields['membres_jury_noms'].initial = '\n'.join(defaults['membres'])
        elif not (self.instance.president_jury_nom or '').strip():
            promo = getattr(self.instance, 'promotion', None)
            if promo and est_promotion_master1_csi_rx(promo):
                defaults = valeurs_jury_m1_defaut()
                self.fields['president_jury_nom'].initial = defaults['president']
                self.fields['secretaire_jury_nom'].initial = defaults['secretaire']
                self.fields['membres_jury_noms'].initial = '\n'.join(defaults['membres'])

    def clean(self):
        cleaned = super().clean()
        type_delib = cleaned.get('type_deliberation') or Deliberation.TYPE_SEMESTRIELLE

        if type_delib == Deliberation.TYPE_SEMESTRIELLE:
            if not cleaned.get('session'):
                self.add_error('session', 'La session est obligatoire pour une délibération semestrielle.')
            cleaned['annee_academique'] = None
            cleaned['annee_academique_m1'] = None
            cleaned['semestre1'] = None
            cleaned['semestre2'] = None
        elif type_delib == Deliberation.TYPE_CYCLE_MASTER:
            cleaned['session'] = None
            cleaned['semestre1'] = None
            cleaned['semestre2'] = None
            for field in ('promotion', 'annee_academique', 'annee_academique_m1'):
                if not cleaned.get(field):
                    self.add_error(field, 'Ce champ est obligatoire pour une délibération cycle Master.')
            annee_m1 = cleaned.get('annee_academique_m1')
            annee_m2 = cleaned.get('annee_academique')
            if annee_m1 and annee_m2 and annee_m1.annee_debut >= annee_m2.annee_debut:
                self.add_error(
                    'annee_academique_m1',
                    'L’année Master 1 doit être antérieure à l’année Master 2.',
                )
        else:
            cleaned['session'] = None
            cleaned['annee_academique_m1'] = None
            for field in ('annee_academique', 'semestre1', 'semestre2', 'promotion'):
                if not cleaned.get(field):
                    self.add_error(field, 'Ce champ est obligatoire pour une délibération annuelle.')
            s1, s2 = cleaned.get('semestre1'), cleaned.get('semestre2')
            if s1 and s2:
                if s1.pk == s2.pk:
                    self.add_error('semestre2', 'Choisissez deux semestres distincts.')
                elif s1.numero > s2.numero:
                    cleaned['semestre1'], cleaned['semestre2'] = s2, s1

        return cleaned


class DecisionJuryForm(forms.ModelForm):
    class Meta:
        model = DecisionJury
        fields = [
            'deliberation', 'etudiant', 'inscription', 'decision',
            'moyenne_semestre', 'moyenne_semestre1', 'moyenne_semestre2',
            'credits_obtenus', 'credits_totaux', 'credits_semestre1', 'credits_semestre2',
            'rang', 'mention', 'notes_jury'
        ]
        widgets = {
            'deliberation': forms.Select(attrs={'class': 'form-control'}),
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'inscription': forms.Select(attrs={'class': 'form-control'}),
            'decision': forms.Select(attrs={'class': 'form-control'}),
            'moyenne_semestre': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 20}),
            'moyenne_semestre1': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 20}),
            'moyenne_semestre2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 20}),
            'credits_obtenus': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'credits_totaux': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0, 'value': 30.0}),
            'credits_semestre1': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'credits_semestre2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'rang': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'mention': forms.Select(attrs={'class': 'form-control'}),
            'notes_jury': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DetteListFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Rechercher',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'N°, nom, prénom…',
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
        label='Promotion actuelle',
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

    def _optional_pk(self, key):
        if not self.data:
            return None
        value = self.data.get(key)
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def __init__(self, *args, annee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.annee = annee or AnneeAcademique.get_active()

        filiere = None
        promotion = None
        if self.data:
            filiere_id = self._optional_pk('filiere')
            if filiere_id:
                filiere = Filiere.objects.filter(pk=filiere_id).first()
            promotion_id = self._optional_pk('promotion')
            if promotion_id:
                promotion = Promotion.objects.filter(pk=promotion_id).first()

        promotion_qs = Promotion.objects.filter(active=True, ordre__gte=2).select_related('filiere')
        if filiere:
            promotion_qs = promotion_qs.filter(filiere=filiere)
        if self.annee:
            promotion_qs = promotion_qs.filter(
                classes__inscriptions__annee_academique=self.annee,
            ).distinct()
        self.fields['promotion'].queryset = promotion_qs.order_by('filiere__code', 'ordre', 'code')

        classe_qs = (
            Classe.objects.filter(active=True, promotion__ordre__gte=2)
            .select_related('promotion', 'promotion__filiere')
            .order_by('promotion__filiere__code', 'promotion__ordre', 'promotion__code', 'code')
        )
        if self.annee:
            classe_qs = classe_qs.filter(
                inscriptions__annee_academique=self.annee,
            ).distinct()
        if filiere:
            classe_qs = classe_qs.filter(promotion__filiere=filiere)
        if promotion:
            classe_qs = classe_qs.filter(promotion=promotion)
        self.fields['classe'].queryset = classe_qs

        self.fields['filiere'].label_from_instance = lambda obj: obj.code
        self.fields['promotion'].label_from_instance = (
            lambda obj: f'{obj.filiere.code} — {obj.code} ({obj.nom})'
        )
        self.fields['classe'].label_from_instance = (
            lambda obj: f'{obj.promotion.code} — {obj.code}'
        )


class JuryMemberAddForm(forms.Form):
    utilisateur = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Utilisateur',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    def __init__(self, *args, exclude_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True).order_by('last_name', 'first_name', 'username')
        if exclude_ids:
            qs = qs.exclude(pk__in=exclude_ids)
        self.fields['utilisateur'].queryset = qs
        self.fields['utilisateur'].label_from_instance = (
            lambda u: u.get_full_name().strip() or u.username
        )
