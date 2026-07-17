"""Filtres d'affichage monétaire (CDF)."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def format_montant_cdf(value, avec_devise=True):
    """
    Formate un montant entier avec séparateur d'espace (ex. 15 000 CDF).
    """
    if value is None or value == "":
        return "—"
    try:
        montant = int(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    texte = f"{montant:,}".replace(",", " ")
    if avec_devise:
        return f"{texte} CDF"
    return texte


@register.filter(name="montant_cdf")
def montant_cdf(value):
    """Montant formaté avec devise : 15 000 CDF."""
    return format_montant_cdf(value, avec_devise=True)


@register.filter(name="montant_espace")
def montant_espace(value):
    """Montant formaté sans devise : 15 000."""
    return format_montant_cdf(value, avec_devise=False)
