import re

from django import forms
from django.utils import timezone

from academics.models import AnneeAcademique, Semestre
from students.models import Inscription

from .models import MotifPaiement, Paiement


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
        self.fields['semestre'].required = False
        self.fields['semestre'].empty_label = 'Année entière'
        self.fields['devise'].label = 'Devise du montant'
        self.fields['nom'].required = False
        self.fields['nom'].help_text = (
            'Laissé vide : libellé généré automatiquement (ex. Enrôlement session principale — S1).'
        )
        if self.instance.pk and self.instance.contexte not in MotifPaiement.CONTEXTES_ANNUELS:
            self.fields['semestre'].disabled = True
            self.fields['contexte'].disabled = True
            self.fields['semestre'].help_text = 'Non modifiable — supprimez et recréez le motif pour changer de semestre.'
            self.fields['contexte'].help_text = 'Non modifiable — un seul motif par semestre et par type de session.'
        elif self.instance.pk:
            self.fields['contexte'].disabled = True
            self.fields['semestre'].disabled = True

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            cleaned['semestre'] = self.instance.semestre
            cleaned['contexte'] = self.instance.contexte

        semestre = cleaned.get('semestre')
        contexte = cleaned.get('contexte')
        annuel = contexte in MotifPaiement.CONTEXTES_ANNUELS

        if annuel:
            cleaned['semestre'] = None
            semestre = None
        elif not semestre:
            self.add_error('semestre', 'Le semestre est obligatoire pour un enrôlement.')
        if not self.annee_active:
            raise forms.ValidationError(
                'Aucune année académique active. Définissez l\'année en cours dans la structure académique.',
            )

        if contexte and self.annee_active and (annuel or semestre):
            conflit = MotifPaiement.objects.filter(
                annee_academique=self.annee_active,
                contexte=contexte,
            ).exclude(pk=self.instance.pk)
            if annuel:
                conflit = conflit.filter(semestre__isnull=True)
            else:
                conflit = conflit.filter(semestre=semestre)
            conflit = conflit.first()
            if conflit:
                libelle = dict(MotifPaiement.CONTEXTE_CHOICES).get(contexte, contexte)
                raise forms.ValidationError(
                    f'Un motif « {libelle} » existe déjà ({conflit.code}). '
                    f'Modifiez ce motif existant ou choisissez une autre combinaison.'
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


class MotifMontantWidget(forms.Select):
    def __init__(self, attrs=None, choices=(), montants=None):
        self.montants = montants or {}
        super().__init__(attrs, choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs,
        )
        info = self.montants.get(str(option.get('value') or ''))
        if info:
            option['attrs']['data-montant'] = info['montant']
            option['attrs']['data-devise'] = info['devise']
        return option


class InscriptionPaiementField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        etudiant = obj.etudiant
        faculte = ''
        classe = getattr(obj, 'classe', None)
        promotion = getattr(classe, 'promotion', None)
        filiere = getattr(promotion, 'filiere', None)
        if filiere and filiere.faculte_id:
            faculte = filiere.faculte.code
        suffixe = f' — {faculte}' if faculte else ''
        return f'{etudiant.numero_etudiant} — {etudiant.prenom} {etudiant.nom}{suffixe}'


class PaiementForm(forms.ModelForm):
    inscription = InscriptionPaiementField(
        queryset=Inscription.objects.none(),
        label='Étudiant',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Paiement
        fields = [
            'inscription',
            'motif_paiement',
            'montant',
            'devise',
            'mode',
            'operateur',
            'telephone',
            'reference_transaction',
            'carte_masquee',
            'statut',
            'date_paiement',
            'observation',
        ]
        widgets = {
            'motif_paiement': forms.Select(attrs={'class': 'form-control'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'devise': forms.Select(attrs={'class': 'form-control'}),
            'mode': forms.Select(attrs={'class': 'form-control'}),
            'operateur': forms.Select(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '099… ou +243…',
                'inputmode': 'tel',
            }),
            'reference_transaction': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code SMS ou autorisation carte',
            }),
            'carte_masquee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1234',
                'maxlength': '4',
                'inputmode': 'numeric',
                'autocomplete': 'off',
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'date_paiement': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-control', 'type': 'datetime-local'},
            ),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, annee_active=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.annee_active = annee_active or AnneeAcademique.get_active()
        inscriptions = Inscription.objects.none()
        if self.annee_active:
            inscriptions = (
                Inscription.objects.filter(annee_academique=self.annee_active)
                .eligibles_listes()
                .select_related(
                    'etudiant',
                    'classe__promotion__filiere__faculte',
                    'annee_academique',
                )
                .order_by('etudiant__numero_etudiant')
            )
        self.fields['inscription'].queryset = inscriptions
        motifs = MotifPaiement.objects.filter(active=True).select_related('semestre', 'annee_academique')
        if self.annee_active:
            motifs = motifs.filter(annee_academique=self.annee_active)
        else:
            motifs = motifs.none()
        motifs = motifs.order_by('semestre__numero', 'contexte')
        montants = {
            str(motif.pk): {'montant': f'{motif.montant:.2f}', 'devise': motif.devise}
            for motif in motifs
        }
        self.fields['motif_paiement'].widget = MotifMontantWidget(
            attrs={'class': 'form-control'},
            montants=montants,
        )
        self.fields['motif_paiement'].queryset = motifs
        self.fields['motif_paiement'].label = 'Frais'
        self.fields['operateur'].required = False
        self.fields['telephone'].required = False
        self.fields['reference_transaction'].required = False
        self.fields['carte_masquee'].required = False
        self.fields['observation'].required = False
        self.fields['date_paiement'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]
        if self.instance.pk and self.instance.date_paiement:
            self.initial['date_paiement'] = timezone.localtime(self.instance.date_paiement).strftime('%Y-%m-%dT%H:%M')
        elif not self.initial.get('date_paiement'):
            self.initial['date_paiement'] = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    def clean_montant(self):
        montant = self.cleaned_data.get('montant')
        if montant is None or montant <= 0:
            raise forms.ValidationError('Le montant doit être supérieur à zéro.')
        return montant

    def clean_carte_masquee(self):
        valeur = (self.cleaned_data.get('carte_masquee') or '').strip()
        if not valeur:
            return ''
        if not re.fullmatch(r'\d{4}', valeur):
            raise forms.ValidationError('Indiquez uniquement les 4 derniers chiffres de la carte.')
        return valeur

    def clean_telephone(self):
        valeur = re.sub(r'[\s.-]', '', (self.cleaned_data.get('telephone') or '').strip())
        if valeur and not re.fullmatch(r'\+?\d{8,15}', valeur):
            raise forms.ValidationError('Numéro mobile money invalide.')
        return valeur

    def clean(self):
        cleaned = super().clean()
        inscription = cleaned.get('inscription')
        motif = cleaned.get('motif_paiement')
        mode = cleaned.get('mode')
        devise = cleaned.get('devise')
        montant = cleaned.get('montant')

        if inscription and motif and inscription.annee_academique_id != motif.annee_academique_id:
            self.add_error(
                'motif_paiement',
                'Ce frais ne concerne pas l\'année de l\'inscription.',
            )
        if devise == MotifPaiement.DEVISE_CDF and montant and montant % 1:
            self.add_error('montant', 'En CDF, saisissez un montant entier (sans centimes).')
        if motif and devise and motif.devise != devise:
            self.add_error(
                'devise',
                f'Ce frais est libellé en {motif.get_devise_display()}.',
            )

        if mode == Paiement.MODE_MOBILE_MONEY:
            if not cleaned.get('operateur'):
                self.add_error('operateur', 'Choisissez l\'opérateur mobile money.')
            if not cleaned.get('telephone'):
                self.add_error('telephone', 'Le numéro mobile money est obligatoire.')
            if not (cleaned.get('reference_transaction') or '').strip():
                self.add_error('reference_transaction', 'La référence de la transaction est obligatoire.')
        elif mode == Paiement.MODE_CARTE:
            if not (cleaned.get('reference_transaction') or '').strip():
                self.add_error('reference_transaction', 'La référence d\'autorisation de la carte est obligatoire.')
        return cleaned


class PaiementEtudiantForm(PaiementForm):
    """Déclaration de paiement par l'étudiant : mobile money ou carte bancaire."""

    def __init__(self, *args, etudiant=None, **kwargs):
        self.etudiant = etudiant
        super().__init__(*args, **kwargs)
        self.fields.pop('statut', None)
        self.fields.pop('date_paiement', None)
        self.fields.pop('observation', None)
        self.fields['inscription'].label = 'Inscription'
        self.fields['mode'].choices = [
            (Paiement.MODE_MOBILE_MONEY, 'Mobile money'),
            (Paiement.MODE_CARTE, 'Carte bancaire'),
        ]
        if etudiant is not None:
            self.fields['inscription'].queryset = (
                self.fields['inscription'].queryset.filter(etudiant=etudiant)
            )
        self.fields['motif_paiement'].label_from_instance = self.libelle_frais

    @staticmethod
    def libelle_frais(motif):
        """Un seul libellé, sans répéter le contexte ni le semestre."""
        nom = (motif.nom or '').strip()
        contexte = motif.get_contexte_display().strip()
        if not nom:
            libelle = contexte
        elif nom.casefold().startswith(contexte.casefold()):
            libelle = nom
        else:
            libelle = nom
        morceaux = []
        vus = set()
        for morceau in libelle.split('—'):
            texte = morceau.strip()
            cle = texte.casefold()
            if texte and cle not in vus:
                vus.add(cle)
                morceaux.append(texte)
        libelle = ' — '.join(morceaux)
        if motif.semestre_id and motif.semestre.code.casefold() not in libelle.casefold():
            libelle = f'{libelle} — {motif.semestre.code}'
        return libelle

    def clean_inscription(self):
        inscription = self.cleaned_data.get('inscription')
        if inscription and self.etudiant and inscription.etudiant_id != self.etudiant.pk:
            raise forms.ValidationError('Cette inscription ne vous appartient pas.')
        return inscription

    def save(self, commit=True):
        paiement = super().save(commit=False)
        paiement.statut = Paiement.STATUT_EN_ATTENTE
        if commit:
            paiement.save()
        return paiement
