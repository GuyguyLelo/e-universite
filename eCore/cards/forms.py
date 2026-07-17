from django import forms
from .models import Card, Personnel, Position, Category


class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = [
            'last_name', 'first_name', 'sex', 'date_of_birth', 'place_of_birth', 'nationality',
            'marital_status', 'current_address', 'phone', 'email',
            'matricule', 'category', 'category_other', 'function_quality', 'position', 'grade',
            'education_level', 'assignment_service', 'contract_type', 'contract_reference',
            'service_start_date',
            'identity_photo_physical', 'identity_photo_digital', 'contract_copy_attached',
            'other_pieces_attached', 'other_pieces_details', 'photo', 'contract_file',
            'other_pieces_file',
            'admin_received_by', 'admin_function', 'admin_received_date', 'admin_observations',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'phone': forms.TextInput(attrs={'type': 'tel', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'category_other': forms.TextInput(attrs={'class': 'form-control'}),
            'function_quality': forms.TextInput(attrs={'class': 'form-control'}),
            'grade': forms.TextInput(attrs={'class': 'form-control'}),
            'education_level': forms.TextInput(attrs={'class': 'form-control'}),
            'assignment_service': forms.TextInput(attrs={'class': 'form-control'}),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'contract_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'service_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'identity_photo_physical': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'identity_photo_digital': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contract_copy_attached': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'other_pieces_attached': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'other_pieces_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'matricule': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control', 'capture': 'user'}),
            'contract_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'other_pieces_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'admin_received_by': forms.TextInput(attrs={'class': 'form-control'}),
            'admin_function': forms.TextInput(attrs={'class': 'form-control'}),
            'admin_received_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'admin_observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from prestation.models import BaremePrestation, PersonnelBaremeInitial

        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['sex'].required = True
        self.fields['sex'].choices = Personnel.SEX_CHOICES

        self.baremes_disponibles = list(
            BaremePrestation.objects.filter(active=True).order_by(
                "categorie", "ordre", "intitule"
            )
        )
        self.baremes_quantites = {}
        if self.instance and self.instance.pk:
            for lien in PersonnelBaremeInitial.objects.filter(personnel=self.instance):
                self.baremes_quantites[lien.bareme_id] = lien.quantite

        for bareme in self.baremes_disponibles:
            bareme.est_coche = bareme.pk in self.baremes_quantites
            bareme.quantite_initiale = self.baremes_quantites.get(bareme.pk, 1)
            bareme.display_label = self.bareme_label(bareme)

    @staticmethod
    def bareme_label(bareme):
        montant = f"{int(bareme.montant):,}".replace(",", " ")
        return f"{bareme.intitule} — {bareme.get_categorie_display()} ({montant} CDF)"

    def get_baremes_initiaux_from_post(self, data):
        from prestation.services import parse_baremes_initiaux_post

        return parse_baremes_initiaux_post(data)

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        category = cleaned_data.get('category')
        category_other = (cleaned_data.get('category_other') or '').strip()
        other_pieces_attached = cleaned_data.get('other_pieces_attached')
        other_pieces_details = (cleaned_data.get('other_pieces_details') or '').strip()

        if first_name and last_name:
            qs = Personnel.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Un personnel avec ce prénom et ce nom est déjà enregistré.")

        if category and category.name.lower() == "autre" and not category_other:
            self.add_error('category_other', "Veuillez préciser la catégorie quand « Autre » est sélectionné.")

        if other_pieces_attached and not other_pieces_details:
            self.add_error('other_pieces_details', "Veuillez préciser les autres pièces jointes.")

        return cleaned_data


class PersonnelImportForm(forms.Form):
    fichier_excel = forms.FileField(
        label="Fichier Excel",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx',
        })
    )

class CardForm(forms.ModelForm):
    personnel = forms.ModelChoiceField(
        queryset=Personnel.objects.all(),
        label="Personnel",
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )

    class Meta:
        model = Card
        fields = ['personnel', 'issue_date', 'expiry_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        personnel = cleaned.get('personnel')

        import datetime
        today = datetime.date.today()

        if personnel:
            active_cards = Card.objects.filter(personnel=personnel, expiry_date__gte=today)
            if self.instance and self.instance.pk:
                active_cards = active_cards.exclude(pk=self.instance.pk)

            if active_cards.exists():
                raise forms.ValidationError("Ce personnel possède déjà une carte en cours de validité (non expirée). Impossible de créer une nouvelle carte.")

        return cleaned
