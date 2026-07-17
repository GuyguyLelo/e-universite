"""Contrôle d'accès aux délibérations (gestionnaires vs membres du jury)."""
from django.contrib.auth.models import Group
from django.db.models import Q

from .models import Deliberation

JURY_GROUP_NAME = 'Jury'

JURY_GROUP_PERMISSION_CODENAMES = (
    'view_deliberation',
    'view_decisionjury',
    'change_decisionjury',
)


def user_can_manage_deliberations(user):
    """Accès complet : création, modification, calcul LMD, toutes les délibérations."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return (
        user.has_perm('deliberations.add_deliberation')
        or user.has_perm('deliberations.change_deliberation')
    )


def user_is_jury_member(user, deliberation):
    if not user.is_authenticated:
        return False
    if deliberation.president_jury_id == user.pk:
        return True
    return deliberation.membres_jury.filter(pk=user.pk).exists()


def user_can_access_deliberation(user, deliberation):
    """Consultation d'une délibération (gestionnaire ou membre du jury désigné)."""
    if not user.is_authenticated:
        return False
    if user_can_manage_deliberations(user):
        return True
    if user.has_perm('deliberations.view_deliberation'):
        return user_is_jury_member(user, deliberation)
    return False


def user_can_edit_decision(user, deliberation):
    if not user_can_access_deliberation(user, deliberation):
        return False
    if user_can_manage_deliberations(user):
        return True
    return user.has_perm('deliberations.change_decisionjury')


def deliberations_for_user(user):
    """Délibérations visibles dans les listes."""
    qs = Deliberation.objects.all()
    if user_can_manage_deliberations(user):
        return qs
    if user.has_perm('deliberations.view_deliberation'):
        return qs.filter(
            Q(president_jury=user) | Q(membres_jury=user),
        ).distinct()
    return qs.none()


def get_jury_group():
    return Group.objects.filter(name=JURY_GROUP_NAME).first()


def ensure_jury_group():
    group, _ = Group.objects.get_or_create(name=JURY_GROUP_NAME)
    return group
