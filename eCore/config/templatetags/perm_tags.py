"""
Template tags pour vérifier les droits d'accès (permissions Django).
Utilisation: {% load perm_tags %} puis {% has_perm 'app.view_model' as var %} ou {% has_any_perm 'app.view_x' 'app.view_y' as var %}
"""
from django import template
from django.contrib.auth import get_user_model

User = get_user_model()
register = template.Library()


@register.simple_tag(takes_context=True)
def has_perm(context, perm):
    """Retourne True si l'utilisateur connecté a la permission donnée (ou est superuser)."""
    request = context.get('request')
    if not request or not getattr(request, 'user', None):
        return False
    user = request.user
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(perm)


@register.simple_tag(takes_context=True)
def has_any_perm(context, *perms):
    """Retourne True si l'utilisateur a au moins une des permissions données (ou est superuser)."""
    request = context.get('request')
    if not request or not getattr(request, 'user', None):
        return False
    user = request.user
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return any(user.has_perm(p) for p in perms)
