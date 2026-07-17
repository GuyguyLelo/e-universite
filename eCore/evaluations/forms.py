"""
Formulaires pour l'application evaluations
"""
from django import forms
from django.contrib.auth.models import User
from .models import TypeEvaluation, Session, Evaluation, Note
from academics.models import AnneeAcademique, Semestre, Classe, Filiere, ElementConstitutif
from students.models import Student


def libelle_personnel(personnel):
    if not personnel:
        return ''
    return f'{personnel.last_name} {personnel.first_name}'.strip()


def responsable_user_for_personnel(personnel):
    """Associe un compte utilisateur au professeur (par e-mail)."""
    if not personnel or not personnel.email:
        return None
    email = personnel.email.strip()
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()


def enseignant_ec_info(ec):
    """Libellé enseignant et utilisateur responsable pour un EC."""
    prof = getattr(ec, 'professeur', None)
    label = libelle_personnel(prof) or '—'
    user = responsable_user_for_personnel(prof)
    return label, user


class TypeEvaluationForm(forms.ModelForm):
    class Meta:
        model = TypeEvaluation
        fields = ['code', 'nom', 'description', 'coefficient', 'note_max', 'ordre', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CC, TP, EXAM'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du type'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'value': 1.0}),
            'note_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'max': 20, 'value': 20.0}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            'annee_academique', 'semestre', 'numero', 'code', 'nom', 'date_debut',
            'date_fin', 'date_deliberation', 'deliberation_faite',
            'verrouillee', 'active'
        ]
        widgets = {
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'semestre': forms.Select(attrs={'class': 'form-control'}),
            'numero': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 2}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code automatique si vide'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom automatique si vide'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_deliberation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'deliberation_faite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verrouillee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.order_by('-annee_debut')
        if self.instance.pk:
            self.fields['annee_academique'].disabled = True
        else:
            active = AnneeAcademique.get_active()
            if active:
                self.fields['annee_academique'].initial = active.pk

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk:
            cleaned_data['annee_academique'] = self.instance.annee_academique
        return cleaned_data


class EvaluationForm(forms.ModelForm):
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=True,
        label='Filière',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    enseignant_ec = forms.CharField(
        required=False,
        label='Responsable (enseignant)',
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-light',
            'readonly': 'readonly',
            'id': 'id_enseignant_ec',
            'placeholder': 'Sélectionnez un élément constitutif…',
        }),
    )

    class Meta:
        model = Evaluation
        fields = [
            'ec', 'session', 'type_evaluation', 'code', 'nom',
            'date_evaluation', 'coefficient', 'note_max',
            'responsable', 'notes', 'active'
        ]
        widgets = {
            'ec': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'type_evaluation': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Généré automatiquement',
            }),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom automatique si vide'}),
            'date_evaluation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'value': 1.0}),
            'note_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1, 'max': 20, 'value': 20.0}),
            'responsable': forms.Select(attrs={'class': 'form-control d-none'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['nom'].required = False
        annee = AnneeAcademique.get_active()
        self.fields['session'].queryset = (
            Session.pour_annee(annee)
            .filter(active=True)
            .select_related('semestre', 'annee_academique')
            .order_by('-semestre__numero', '-numero')
        )
        self.fields['session'].label_from_instance = (
            lambda obj: f'{obj.code} — {obj.nom} ({obj.annee_academique.code})'
        )
        self.fields['ec'].label_from_instance = lambda obj: f'{obj.code} — {obj.nom}'
        inclure_type = self.instance.type_evaluation_id if self.instance.pk else None
        self.fields['type_evaluation'].queryset = TypeEvaluation.pour_formulaire_evaluation(
            inclure_pk=inclure_type,
        )
        if not self.instance.pk:
            self.fields['code'].widget = forms.HiddenInput()
            self.fields['code'].initial = ''

        filiere = None
        session = None
        if self.data:
            try:
                filiere_id = int(self.data.get('filiere') or 0)
            except (TypeError, ValueError):
                filiere_id = 0
            if filiere_id:
                filiere = Filiere.objects.filter(pk=filiere_id).first()
            try:
                session_id = int(self.data.get('session') or 0)
            except (TypeError, ValueError):
                session_id = 0
            if session_id:
                session = Session.objects.filter(pk=session_id).select_related('semestre').first()
        elif self.instance.pk:
            if self.instance.ec_id:
                filiere = self.instance.ec.ue.filiere
                self.fields['filiere'].initial = filiere.pk if filiere else None
            session = self.instance.session

        self.fields['ec'].queryset = self._ec_queryset(filiere, session)
        self._apply_enseignant_from_ec(self._selected_ec(filiere, session))

    def _selected_ec(self, filiere, session):
        ec_id = None
        if self.data:
            try:
                ec_id = int(self.data.get('ec') or 0)
            except (TypeError, ValueError):
                ec_id = 0
        elif self.instance.pk and self.instance.ec_id:
            ec_id = self.instance.ec_id
        if not ec_id:
            return None
        return (
            ElementConstitutif.objects.filter(pk=ec_id)
            .select_related('professeur')
            .first()
        )

    def _apply_enseignant_from_ec(self, ec):
        if not ec:
            return
        label, user = enseignant_ec_info(ec)
        self.fields['enseignant_ec'].initial = label
        if user and not self.data:
            self.fields['responsable'].initial = user.pk
        elif user and self.data and not self.data.get('responsable'):
            self.fields['responsable'].initial = user.pk

    @staticmethod
    def _ec_queryset(filiere, session):
        if not filiere or not session:
            return ElementConstitutif.objects.none()
        return (
            ElementConstitutif.objects.filter(
                active=True,
                ue__filiere=filiere,
                ue__semestre=session.semestre,
            )
            .select_related('ue', 'ue__filiere', 'professeur')
            .order_by('ue__ordre', 'ue__code', 'ordre', 'code')
        )

    @property
    def ec_enseignant_map(self):
        mapping = {}
        for ec in self.fields['ec'].queryset:
            label, user = enseignant_ec_info(ec)
            mapping[str(ec.pk)] = {
                'professeur': label,
                'responsable_id': user.pk if user else None,
            }
        return mapping

    @property
    def auto_code_maps(self):
        def codes(field_name):
            return {str(obj.pk): obj.code for obj in self.fields[field_name].queryset}

        return {
            'ec': codes('ec'),
            'session': codes('session'),
            'type_evaluation': codes('type_evaluation'),
        }

    def clean(self):
        cleaned_data = super().clean()
        ec = cleaned_data.get('ec')
        session = cleaned_data.get('session')
        filiere = cleaned_data.get('filiere')
        type_evaluation = cleaned_data.get('type_evaluation')

        if ec and filiere and ec.ue.filiere_id != filiere.id:
            self.add_error('ec', 'Cet élément constitutif n\'appartient pas à la filière sélectionnée.')
        if ec and session and ec.ue.semestre_id != session.semestre_id:
            self.add_error('ec', 'Cet élément constitutif n\'appartient pas au semestre de la session.')

        if ec:
            label, user = enseignant_ec_info(ec)
            cleaned_data['enseignant_ec'] = label
            if user:
                cleaned_data['responsable'] = user

        if ec and session and type_evaluation:
            if not cleaned_data.get('code'):
                cleaned_data['code'] = Evaluation.build_code(ec, session, type_evaluation)
            if not cleaned_data.get('nom'):
                cleaned_data['nom'] = Evaluation.build_nom(type_evaluation, ec, session)
        return cleaned_data


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = [
            'etudiant', 'evaluation', 'note', 'note_sur', 'absent',
            'justifie', 'justificatif', 'notes'
        ]
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'evaluation': forms.Select(attrs={'class': 'form-control'}),
            'note': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 10}),
            'note_sur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0.01, 'max': 10, 'value': 10.0}),
            'absent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'justifie': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'justificatif': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        evaluation = cleaned.get('evaluation')
        note = cleaned.get('note')
        absent = cleaned.get('absent')
        if evaluation and note is not None and not absent:
            from .calcul_notes import plafond_note_saisie, valider_note_saisie
            try:
                valider_note_saisie(note, evaluation)
            except ValueError as exc:
                self.add_error('note', str(exc))
            else:
                plafond = plafond_note_saisie(evaluation)
                if not cleaned.get('note_sur'):
                    cleaned['note_sur'] = plafond
        return cleaned


class NoteImportExcelForm(forms.Form):
    fichier_excel = forms.FileField(
        label='Fichier Excel',
        widget=forms.FileInput(attrs={
            'class': 'form-control form-control-sm',
            'accept': '.xlsx',
        }),
    )


class EvaluationListFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Rechercher',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Code, nom, EC…',
        }),
    )
    semestre = forms.ModelChoiceField(
        queryset=Semestre.objects.filter(active=True).order_by('numero'),
        required=False,
        label='Semestre',
        empty_label='Tous les semestres',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label='Filière',
        empty_label='Toutes les filières',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    session = forms.ModelChoiceField(
        queryset=Session.objects.none(),
        required=False,
        label='Session',
        empty_label='Toutes les sessions',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    type_evaluation = forms.ModelChoiceField(
        queryset=TypeEvaluation.objects.none(),
        required=False,
        label="Type d'évaluation",
        empty_label='Tous les types',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    ec = forms.ModelChoiceField(
        queryset=ElementConstitutif.objects.none(),
        required=False,
        label='Cours (UE / EC)',
        empty_label='Tous les cours',
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
        annee = annee or AnneeAcademique.get_active()

        semestre = None
        filiere = None
        session = None
        if self.data:
            semestre_id = self._optional_pk('semestre')
            if semestre_id:
                semestre = Semestre.objects.filter(pk=semestre_id).first()
            filiere_id = self._optional_pk('filiere')
            if filiere_id:
                filiere = Filiere.objects.filter(pk=filiere_id).first()
            session_id = self._optional_pk('session')
            if session_id:
                session = Session.objects.filter(pk=session_id).select_related('semestre').first()

        session_qs = (
            Session.pour_annee(annee)
            .filter(active=True)
            .select_related('semestre', 'annee_academique')
            .order_by('-semestre__numero', '-numero')
        )
        if semestre:
            session_qs = session_qs.filter(semestre=semestre)
        elif filiere:
            session_qs = session_qs.filter(semestre__ues__filiere=filiere).distinct()
        self.fields['session'].queryset = session_qs

        ec_qs = ElementConstitutif.objects.filter(active=True).select_related('ue', 'ue__filiere')
        if semestre:
            ec_qs = ec_qs.filter(ue__semestre=semestre)
        if filiere:
            ec_qs = ec_qs.filter(ue__filiere=filiere)
        if session:
            ec_qs = ec_qs.filter(ue__semestre=session.semestre)
        self.fields['ec'].queryset = ec_qs.order_by('ue__ordre', 'ue__code', 'ordre', 'code')

        self.fields['type_evaluation'].queryset = (
            TypeEvaluation.objects.filter(active=True).order_by('ordre', 'nom')
        )

        self.fields['semestre'].label_from_instance = lambda obj: f'{obj.code} — {obj.nom}'
        self.fields['filiere'].label_from_instance = lambda obj: obj.code
        self.fields['session'].label_from_instance = lambda obj: f'{obj.code} — {obj.nom}'
        self.fields['type_evaluation'].label_from_instance = lambda obj: obj.nom
        self.fields['ec'].label_from_instance = lambda obj: f'{obj.code} — {obj.nom}'


class NoteConsultationFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Rechercher',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'N° étudiant, nom, prénom…',
        }),
    )
    session = forms.ModelChoiceField(
        queryset=Session.objects.none(),
        required=False,
        label='Session',
        empty_label='Toutes les sessions',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(active=True).order_by('code'),
        required=False,
        label='Filière',
        empty_label='Toutes les filières',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label='Classe',
        empty_label='Toutes les classes',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    ec = forms.ModelChoiceField(
        queryset=ElementConstitutif.objects.none(),
        required=False,
        label='Cours (UE / EC)',
        empty_label='Tous les cours',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    evaluation = forms.ModelChoiceField(
        queryset=Evaluation.objects.none(),
        required=False,
        label='Évaluation',
        empty_label='Toutes les évaluations',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    presence = forms.ChoiceField(
        required=False,
        label='Présence',
        choices=[
            ('', 'Tous'),
            ('present', 'Présents'),
            ('absent', 'Absents'),
            ('justifie', 'Absents justifiés'),
            ('non_justifie', 'Absents non justifiés'),
        ],
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeAcademique.get_active()
        self.fields['session'].queryset = (
            Session.pour_annee(annee)
            .filter(active=True)
            .select_related('semestre', 'annee_academique')
            .order_by('-semestre__numero', '-numero')
        )

        session = None
        filiere = None
        ec = None
        if self.data:
            session_id = self._optional_pk('session')
            if session_id:
                session = Session.objects.filter(pk=session_id).select_related('semestre').first()
            filiere_id = self._optional_pk('filiere')
            if filiere_id:
                filiere = Filiere.objects.filter(pk=filiere_id).first()
            ec_id = self._optional_pk('ec')
            if ec_id:
                ec = ElementConstitutif.objects.filter(pk=ec_id).select_related('ue').first()

        classe_qs = (
            Classe.objects.filter(active=True)
            .select_related('promotion', 'promotion__filiere')
            .order_by('promotion__filiere__code', 'promotion__code', 'code')
        )
        if filiere:
            classe_qs = classe_qs.filter(promotion__filiere=filiere)
        self.fields['classe'].queryset = classe_qs

        ec_qs = ElementConstitutif.objects.filter(active=True).select_related('ue', 'ue__filiere')
        if session:
            ec_qs = ec_qs.filter(ue__semestre=session.semestre)
        if filiere:
            ec_qs = ec_qs.filter(ue__filiere=filiere)
        self.fields['ec'].queryset = ec_qs.order_by('ue__ordre', 'ue__code', 'ordre', 'code')

        eval_qs = (
            Evaluation.objects.filter(active=True)
            .select_related('type_evaluation', 'ec', 'session')
        )
        if session:
            eval_qs = eval_qs.filter(session=session)
        if ec:
            eval_qs = eval_qs.filter(ec=ec)
        self.fields['evaluation'].queryset = eval_qs.order_by(
            'type_evaluation__ordre', 'type_evaluation__nom', 'code',
        )

        self.fields['session'].label_from_instance = (
            lambda obj: f'{obj.code} — {obj.nom} ({obj.annee_academique.code})'
        )
        self.fields['classe'].label_from_instance = (
            lambda obj: f'{obj.promotion.nom} — {obj.code}'
        )
        self.fields['ec'].label_from_instance = lambda obj: f'{obj.code} — {obj.nom}'
        self.fields['evaluation'].label_from_instance = (
            lambda obj: f'{obj.type_evaluation.nom} — {obj.ec.code} ({obj.session.code})'
        )
