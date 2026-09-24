from django import forms
from .models import Card, Personnel, Position, Category, Grade


class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = [
            'last_name', 'first_name', 'sex', 'date_of_birth', 'place_of_birth', 'nationality',
            'marital_status', 'current_address', 'phone', 'email',
            'matricule', 'category', 'category_other', 'function_quality', 'position', 'grade',
            'education_level', 'assignment_service', 'contract_type', 'contract_reference',
            'service_start_date',
            'identity_photo_physical', 'other_pieces_details', 'photo', 'contract_file',
            'other_pieces_file',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'required': True, 'placeholder': 'Nom', 'autocomplete': 'family-name'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom', 'autocomplete': 'given-name'}),
            'sex': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ville'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Congolaise'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse actuelle'}),
            'phone': forms.TextInput(attrs={'type': 'tel', 'class': 'form-control', 'placeholder': '+243 …', 'autocomplete': 'tel'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'nom@exemple.cd', 'autocomplete': 'email'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'category_other': forms.TextInput(attrs={'class': 'form-control'}),
            'function_quality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex. chef de département'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'education_level': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex. doctorat'}),
            'assignment_service': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Faculté, secrétariat, service…'}),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'contract_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° de l’acte ou du contrat'}),
            'service_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'identity_photo_physical': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'other_pieces_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Diplômes, attestation…'}),
            'matricule': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control', 'capture': 'user'}),
            'contract_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'other_pieces_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['sex'].required = True
        self.fields['sex'].choices = Personnel.SEX_CHOICES
        self.fields['grade'].queryset = Grade.objects.order_by('ordre', 'nom')
        self.fields['grade'].empty_label = "—"
        self.fields['position'].queryset = Position.objects.order_by('name')
        self.fields['position'].empty_label = "—"
        self.fields['category'].queryset = Category.objects.order_by('name')
        self.fields['category'].empty_label = "—"

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        category = cleaned_data.get('category')
        category_other = (cleaned_data.get('category_other') or '').strip()

        if first_name and last_name:
            qs = Personnel.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Un personnel avec ce prénom et ce nom est déjà enregistré.")

        if category and category.name.lower() == "autre" and not category_other:
            self.add_error('category_other', "Veuillez préciser la catégorie quand « Autre » est sélectionné.")

        return cleaned_data

    def save(self, commit=True):
        personnel = super().save(commit=False)
        personnel.identity_photo_digital = bool(personnel.photo)
        personnel.contract_copy_attached = bool(personnel.contract_file)
        personnel.other_pieces_attached = bool(personnel.other_pieces_file) or bool(
            (personnel.other_pieces_details or '').strip()
        )
        if commit:
            personnel.save()
            self.save_m2m()
        return personnel


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
