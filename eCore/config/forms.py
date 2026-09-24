from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import Etablissement

LOGO_TYPES = {'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
LOGO_MAX_OCTETS = 2 * 1024 * 1024


class EtablissementForm(forms.ModelForm):
    class Meta:
        model = Etablissement
        fields = [
            'code', 'nom', 'statut_juridique', 'categorie', 'phase', 'logo',
            'province', 'ville', 'adresse', 'telephone', 'email', 'site_web',
            'tutelle', 'numero_agrement', 'date_agrement', 'promoteur', 'actif',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UNIKIN'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom officiel de l'établissement"}),
            'statut_juridique': forms.Select(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'phase': forms.Select(attrs={'class': 'form-control'}),
            'province': forms.Select(attrs={'class': 'form-control'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control'}),
            'tutelle': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_agrement': forms.TextInput(attrs={'class': 'form-control'}),
            'date_agrement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'promoteur': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/png,image/jpeg,image/webp,image/gif',
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        widget = self.fields['logo'].widget
        widget.clear_checkbox_label = 'Retirer le logo'
        widget.initial_text = 'Logo actuel'
        widget.input_text = 'Remplacer'

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if not logo or logo is False:
            return logo
        content_type = getattr(logo, 'content_type', '')
        if content_type and content_type not in LOGO_TYPES:
            raise ValidationError('Le logo doit être une image PNG, JPEG, WebP ou GIF.')
        if getattr(logo, 'size', 0) > LOGO_MAX_OCTETS:
            raise ValidationError('Le logo ne doit pas dépasser 2 Mo.')
        return logo


class ConnexionForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "Identifiant ou mot de passe incorrect. "
            "Les majuscules et les minuscules sont prises en compte."
        ),
        "inactive": "Ce compte est désactivé.",
    }

    def get_invalid_login_error(self):
        return ValidationError(
            self.error_messages["invalid_login"],
            code="invalid_login",
        )

    def clean(self):
        from django.contrib.auth.models import User
        from students.compte import resoudre_identifiant, variantes_mot_de_passe

        username = (self.cleaned_data.get("username") or "").strip()
        if username:
            resolu = resoudre_identifiant(username)
            if resolu:
                self.cleaned_data["username"] = resolu
                username = resolu
        mot_de_passe = self.cleaned_data.get("password") or ""
        utilisateur = User.objects.filter(username=username).first() if username else None
        if utilisateur and mot_de_passe and not utilisateur.check_password(mot_de_passe):
            for variante in variantes_mot_de_passe(mot_de_passe):
                if utilisateur.check_password(variante):
                    self.cleaned_data["password"] = variante
                    break
        return super().clean()
