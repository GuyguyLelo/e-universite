"""Services métier — formation continue."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import Inscription, Presence, SessionFormation


def resume_session_pour_cloture(session: SessionFormation) -> dict:
    """Indicateurs affichés avant / après clôture d'une session."""
    inscriptions = session.inscriptions.select_related('seminariste')
    nb_inscrits = inscriptions.count()
    nb_abandon = inscriptions.filter(statut=Inscription.STATUT_ABANDON).count()
    nb_actifs = nb_inscrits - nb_abandon
    brevets_ids = set(session.brevets.values_list('seminariste_id', flat=True))
    nb_brevets = len(brevets_ids)
    nb_presences = Presence.objects.filter(offre_module__session=session).count()
    nb_presents = Presence.objects.filter(
        offre_module__session=session,
        statut__in=[Presence.STATUT_PRESENT, Presence.STATUT_RETARD],
    ).count()
    sans_brevet = (
        inscriptions.exclude(statut=Inscription.STATUT_ABANDON)
        .exclude(seminariste_id__in=brevets_ids)
        .select_related('seminariste')
    )
    return {
        'nb_inscrits': nb_inscrits,
        'nb_actifs': nb_actifs,
        'nb_abandon': nb_abandon,
        'nb_brevets': nb_brevets,
        'nb_presences': nb_presences,
        'nb_presents': nb_presents,
        'nb_sans_brevet': sans_brevet.count(),
        'sans_brevet': list(sans_brevet[:50]),
        'brevets_ids': brevets_ids,
        'inscriptions': inscriptions.order_by('seminariste__nom', 'seminariste__prenom'),
    }


@transaction.atomic
def cloturer_session(session: SessionFormation, user, *, observations: str = '') -> SessionFormation:
    """Clôture une session : verrouille et termine les inscriptions actives."""
    if session.cloturee:
        raise ValueError('Cette session est déjà clôturée.')

    session.cloturee = True
    session.active = False
    session.date_cloture = timezone.now()
    session.cloturee_par = user if getattr(user, 'is_authenticated', False) else None
    session.observations_cloture = (observations or '').strip()
    session.save(
        update_fields=[
            'cloturee',
            'active',
            'date_cloture',
            'cloturee_par',
            'observations_cloture',
            'updated_at',
        ]
    )

    session.inscriptions.exclude(statut=Inscription.STATUT_ABANDON).update(
        statut=Inscription.STATUT_TERMINE,
        updated_at=timezone.now(),
    )
    return session
