from datetime import date

from django import forms

from academics.models import Classe, ElementConstitutif, Local, Section, Semestre
from academics.utils import ActiveAnneeModelFormMixin
from cards.models import Personnel

from .models import BaremePrestation, EnveloppeBudgetaire, Horaire, HoraireLigne, Prestation


MONTH_CHOICES = [
    ("1", "Janvier"),
    ("2", "Février"),
    ("3", "Mars"),
    ("4", "Avril"),
    ("5", "Mai"),
    ("6", "Juin"),
    ("7", "Juillet"),
    ("8", "Août"),
    ("9", "Septembre"),
    ("10", "Octobre"),
    ("11", "Novembre"),
    ("12", "Décembre"),
]


def _annee_choices():
    current = date.today().year
    return [(year, str(year)) for year in range(current - 5, current + 3)]


class EnveloppeBudgetaireForm(forms.ModelForm):
    class Meta:
        model = EnveloppeBudgetaire
        fields = ["annee", "mois", "montant"]
        widgets = {
            "annee": forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
            "mois": forms.Select(attrs={"class": "form-control"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and "annee" not in self.initial:
            self.initial["annee"] = date.today().year
        self.fields["mois"].choices = EnveloppeBudgetaire.MOIS_CHOICES


class BaremePrestationForm(forms.ModelForm):
    class Meta:
        model = BaremePrestation
        fields = ["categorie", "periode", "intitule", "montant", "ordre", "active"]
        widgets = {
            "categorie": forms.Select(attrs={"class": "form-control"}),
            "periode": forms.Select(attrs={"class": "form-control"}),
            "intitule": forms.TextInput(attrs={"class": "form-control", "placeholder": "Intitulé du barème"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PrestationForm(forms.ModelForm):
    categorie = forms.ChoiceField(
        choices=[("", "---------")] + list(BaremePrestation.CATEGORIE_CHOICES),
        widget=forms.Select(attrs={"class": "form-control", "id": "id_categorie"}),
        label="Type prestation",
    )

    class Meta:
        model = Prestation
        fields = ["date_prestation", "personnel", "categorie", "bareme", "horaire", "observation"]
        widgets = {
            "date_prestation": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "personnel": forms.Select(attrs={"class": "form-control", "id": "id_personnel"}),
            "bareme": forms.Select(attrs={"class": "form-control", "id": "id_bareme"}),
            "horaire": forms.Select(attrs={"class": "form-control"}),
            "observation": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["horaire"].required = False
        self.fields["bareme"].queryset = BaremePrestation.objects.none()
        self.fields["bareme"].required = True
        selected_categorie = self.data.get("categorie") if self.is_bound else None
        if selected_categorie:
            self.fields["bareme"].queryset = BaremePrestation.objects.filter(
                categorie=selected_categorie, active=True
            ).order_by("ordre", "intitule")
        elif self.instance and self.instance.pk and self.instance.bareme_id:
            self.fields["categorie"].initial = self.instance.categorie
            self.fields["bareme"].queryset = BaremePrestation.objects.filter(
                categorie=self.instance.categorie, active=True
            ).order_by("ordre", "intitule")

    def clean(self):
        cleaned = super().clean()
        bareme = cleaned.get("bareme")
        categorie = cleaned.get("categorie")
        if bareme and categorie and bareme.categorie != categorie:
            self.add_error("bareme", "Le barème sélectionné ne correspond pas au type de prestation choisi.")
        date_prestation = cleaned.get("date_prestation")
        if date_prestation:
            from .services import get_enveloppe_for_date

            if not get_enveloppe_for_date(date_prestation):
                self.add_error(
                    "date_prestation",
                    "Aucune enveloppe budgétaire n'a été trouvée.",
                )
        return cleaned


class CloturePaieForm(forms.Form):
    annee = forms.TypedChoiceField(
        choices=[],
        coerce=int,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    mois = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = _annee_choices()
        if not self.is_bound:
            self.fields["annee"].initial = date.today().year


class CalculPaieForm(forms.Form):
    annee = forms.TypedChoiceField(
        choices=[],
        coerce=int,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    mois = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = _annee_choices()
        if not self.is_bound:
            self.fields["annee"].initial = date.today().year


class PrestationMensuelleSaisieForm(forms.Form):
    mois = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    annee = forms.TypedChoiceField(
        choices=[],
        coerce=int,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    numero_fiche = forms.CharField(
        label="Numéro de fiche",
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. FIC-2026-001"}),
    )
    personnel = forms.ModelChoiceField(
        queryset=Personnel.objects.order_by("last_name", "first_name"),
        label="Personnel",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    bareme = forms.ModelChoiceField(
        queryset=BaremePrestation.objects.none(),
        label="Barème",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    quantite = forms.IntegerField(
        label="Quantité",
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "step": 1}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services import get_baremes_prestation_mensuelle_queryset

        self.fields["annee"].choices = _annee_choices()
        self.fields["bareme"].queryset = get_baremes_prestation_mensuelle_queryset()
        self.fields["bareme"].label_from_instance = self._bareme_label

        if not self.is_bound:
            today = date.today()
            self.initial.setdefault("mois", str(today.month))
            self.initial.setdefault("annee", today.year)

    @staticmethod
    def _bareme_label(bareme):
        montant = f"{int(bareme.montant):,}".replace(",", " ")
        return f"{bareme.intitule} — {bareme.get_categorie_display()} ({montant} CDF)"

    def clean(self):
        cleaned = super().clean()
        annee = cleaned.get("annee")
        mois = cleaned.get("mois")
        bareme = cleaned.get("bareme")

        if annee and mois:
            from .services import assert_enveloppe_disponible, get_enveloppe_for_date

            try:
                date_controle = date(int(annee), int(mois), 1)
            except (TypeError, ValueError):
                self.add_error("mois", "Mois ou année invalide.")
            else:
                if not get_enveloppe_for_date(date_controle):
                    self.add_error(
                        "mois",
                        "Aucune enveloppe budgétaire n'a été trouvée pour cette période.",
                    )
                else:
                    try:
                        assert_enveloppe_disponible(date_controle)
                    except ValueError as exc:
                        self.add_error("mois", str(exc))

        if bareme and bareme.categorie == BaremePrestation.CATEGORIE_ENSEIGNEMENT:
            self.add_error("bareme", "Les barèmes de type enseignement ne sont pas autorisés ici.")

        return cleaned


class PrestationMensuelleListeForm(forms.Form):
    mois = forms.ChoiceField(
        choices=[("", "Tous les mois")] + MONTH_CHOICES,
        required=False,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    annee = forms.ChoiceField(
        choices=[],
        required=False,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    numero_fiche = forms.CharField(
        required=False,
        label="Numéro de fiche",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Filtrer par fiche"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = [("", "Toutes les années")] + [
            (str(year), str(year)) for year, _ in _annee_choices()
        ]
        if not self.is_bound:
            today = date.today()
            self.initial.setdefault("mois", str(today.month))
            self.initial.setdefault("annee", str(today.year))


class PrestationDepuisHoraireListeForm(forms.Form):
    mois = forms.ChoiceField(
        choices=[("", "Tous les mois")] + MONTH_CHOICES,
        required=False,
        label="Mois",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    annee = forms.ChoiceField(
        choices=[],
        required=False,
        label="Année",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    numero_fiche = forms.CharField(
        required=False,
        label="Numéro de fiche",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Filtrer par fiche"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.filter(active=True).order_by("code"),
        required=False,
        label="Section",
        empty_label="Toutes les sections",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["annee"].choices = [("", "Toutes les années")] + [
            (str(year), str(year)) for year, _ in _annee_choices()
        ]
        if not self.is_bound:
            today = date.today()
            self.initial.setdefault("mois", str(today.month))
            self.initial.setdefault("annee", str(today.year))


class PrestationDepuisHoraireFiltreForm(forms.Form):
    """Filtre d'affichage de l'horaire : fiche, section et jour uniquement."""

    JOUR_CHOICES = [
        ("lundi", "Lundi"),
        ("mardi", "Mardi"),
        ("mercredi", "Mercredi"),
        ("jeudi", "Jeudi"),
        ("vendredi", "Vendredi"),
        ("samedi", "Samedi"),
    ]

    numero_fiche = forms.CharField(
        label="Numéro fiche",
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. FIC-2026-001"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.filter(active=True).order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    jour = forms.ChoiceField(
        choices=JOUR_CHOICES,
        label="Jour",
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class PrestationDepuisHoraireDateForm(forms.Form):
    """Date figurant sur la fiche : enregistrée comme date de la prestation (hors filtre horaire)."""

    date_prestation = forms.DateField(
        label="Date de la prestation",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date", "id": "id_date_prestation"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("date_prestation", date.today())


class FichePrestationJournaliereForm(forms.Form):
    JOUR_CHOICES = [
        ("lundi", "Lundi"),
        ("mardi", "Mardi"),
        ("mercredi", "Mercredi"),
        ("jeudi", "Jeudi"),
        ("vendredi", "Vendredi"),
        ("samedi", "Samedi"),
    ]

    jour = forms.ChoiceField(
        choices=JOUR_CHOICES,
        label="Jour",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    semestre = forms.ModelChoiceField(
        queryset=Semestre.objects.order_by("numero"),
        label="Semestre",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["semestre"].queryset = Semestre.objects.order_by("numero")


class StatistiquesPrestationEnseignementForm(forms.Form):
    date_debut = forms.DateField(
        label="Du",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    date_fin = forms.DateField(
        label="Au",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    semestre = forms.ModelChoiceField(
        queryset=Semestre.objects.order_by("numero"),
        label="Semestre",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.all().order_by("code"),
        label="Section",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["semestre"].queryset = Semestre.objects.order_by("numero")

    def clean(self):
        cleaned = super().clean()
        date_debut = cleaned.get("date_debut")
        date_fin = cleaned.get("date_fin")
        if date_debut and date_fin and date_debut > date_fin:
            raise forms.ValidationError("La date de début doit être antérieure ou égale à la date de fin.")
        return cleaned


class HoraireForm(ActiveAnneeModelFormMixin, forms.ModelForm):
    class Meta:
        model = Horaire
        fields = ["titre", "semestre", "classe", "observation", "active"]
        widgets = {
            "titre": forms.TextInput(attrs={"class": "form-control"}),
            "semestre": forms.Select(attrs={"class": "form-control"}),
            "classe": forms.Select(attrs={"class": "form-control"}),
            "observation": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["semestre"].queryset = Semestre.objects.order_by("numero")
        self.fields["classe"].queryset = Classe.objects.select_related("promotion", "promotion__filiere", "promotion__filiere__section", "local").filter(active=True).order_by("promotion__code", "code")


class HoraireLigneForm(forms.ModelForm):
    class Meta:
        model = HoraireLigne
        fields = [
            "jour",
            "heure_debut",
            "heure_fin",
            "ue_code",
            "element_constitutif",
            "local",
            "professeur",
            "ordre",
            "notes",
        ]
        widgets = {
            "jour": forms.Select(attrs={"class": "form-control"}),
            "heure_debut": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "ue_code": forms.HiddenInput(),
            "element_constitutif": forms.Select(attrs={"class": "form-control js-ec-select"}),
            "local": forms.Select(attrs={"class": "form-control"}),
            "professeur": forms.HiddenInput(),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "notes": forms.TextInput(attrs={"class": "form-control", "placeholder": "Observation optionnelle"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["element_constitutif"].queryset = ElementConstitutif.objects.select_related(
            "ue", "ue__semestre", "professeur"
        ).order_by("ue__semestre__numero", "ue__ordre", "ordre", "code")
        self.fields["local"].queryset = Local.objects.filter(active=True).order_by("code")
        self.fields["professeur"].queryset = Personnel.objects.all()
        self.fields["jour"].required = False
        self.fields["heure_debut"].required = False
        self.fields["heure_fin"].required = False
        self.fields["ue_code"].required = False
        self.fields["element_constitutif"].required = False
        self.fields["local"].required = False
        self.fields["professeur"].required = False
        self.fields["ordre"].required = False
        if self.instance and self.instance.element_constitutif_id and not self.instance.professeur_id:
            ec = self.instance.element_constitutif
            if ec.professeur_id:
                self.initial["professeur"] = ec.professeur_id

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned

        jour = cleaned.get("jour")
        heure_debut = cleaned.get("heure_debut")
        heure_fin = cleaned.get("heure_fin")
        ec = cleaned.get("element_constitutif")
        ue_code = (cleaned.get("ue_code") or "").strip()

        if not jour and not heure_debut and not heure_fin and not ec and not ue_code:
            return cleaned

        if not jour:
            raise forms.ValidationError({"jour": "Le jour est obligatoire pour une ligne renseignée."})
        if not heure_debut:
            raise forms.ValidationError({"heure_debut": "L'heure de début est obligatoire."})
        if not heure_fin:
            raise forms.ValidationError({"heure_fin": "L'heure de fin est obligatoire."})

        if not ec and not ue_code:
            raise forms.ValidationError(
                "Veuillez sélectionner un élément constitutif ou renseigner le code UE."
            )
        if heure_debut and heure_fin and heure_fin <= heure_debut:
            raise forms.ValidationError(
                {"heure_fin": "L'heure de fin doit être supérieure à l'heure de début."}
            )

        if ec and ec.professeur_id:
            cleaned["professeur"] = ec.professeur
        elif ec:
            cleaned["professeur"] = None
        if ec and not ue_code and ec.code:
            cleaned["ue_code"] = ec.code
        return cleaned
