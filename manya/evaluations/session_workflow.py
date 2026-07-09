"""
Workflow semestriel : session principale → verrouillage → rattrapage → délibération.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction

from academics.models import AnneeAcademique, ElementConstitutif
from evaluations.calcul_notes import (
    etudiant_convoque_rattrapage,
    note_exam_etudiant_sur_10,
)
from evaluations.models import Session, Evaluation, TypeEvaluation
from students.models import Inscription


class SessionWorkflowError(Exception):
    """Erreur métier du workflow de session."""


def assert_session_writable(session):
    """Lève PermissionDenied si la session est verrouillée."""
    from django.core.exceptions import PermissionDenied
    if session and session.verrouillee:
        raise PermissionDenied('Cette session est verrouillée : la saisie des notes est impossible.')


def session_principale(session):
    """Session principale (numéro 1) du même semestre et de la même année."""
    if session.numero == 1:
        return session
    return Session.objects.filter(
        semestre=session.semestre,
        numero=1,
        annee_academique=session.annee_academique,
    ).first()


def session_rattrapage(session):
    """Session de rattrapage (numéro 2) du même semestre et de la même année."""
    if session.numero == 2:
        return session
    return Session.objects.filter(
        semestre=session.semestre,
        numero=2,
        annee_academique=session.annee_academique,
    ).first()


def _inscriptions_promotion(promotion, annee=None):
    annee = annee or AnneeAcademique.get_active()
    if not annee:
        return Inscription.objects.none()
    return (
        Inscription.objects.filter(
            annee_academique=annee,
            classe__promotion=promotion,
        )
        .eligibles_listes()
        .select_related('etudiant', 'classe')
    )


def _evaluations_exam_session_principale(ec, session_principale):
    return Evaluation.objects.filter(
        ec=ec,
        session=session_principale,
        active=True,
    ).select_related('type_evaluation')


def etudiants_ajournes_ec_ids(ec, session_principale, promotion, annee=None):
    """Étudiants convoqués au rattrapage : note d'examen < 10/10."""
    evaluations = _evaluations_exam_session_principale(ec, session_principale)
    etudiant_ids = []
    for inscription in _inscriptions_promotion(promotion, annee):
        etudiant = inscription.etudiant
        note_exam = note_exam_etudiant_sur_10(etudiant, evaluations)
        if etudiant_convoque_rattrapage(note_exam):
            etudiant_ids.append(etudiant.id)
    return etudiant_ids


def inscriptions_rattrapage_pour_ec(classe, annee, session, ec):
    """Inscriptions convoquées au rattrapage (examen < 10/10) sur l'EC."""
    if session.numero != 2:
        return _inscriptions_classe_base(classe, annee)
    s1 = session_principale(session)
    if not s1:
        return _inscriptions_classe_base(classe, annee)
    ajournes = etudiants_ajournes_ec_ids(ec, s1, classe.promotion, annee)
    return _inscriptions_classe_base(classe, annee).filter(etudiant_id__in=ajournes)


def _inscriptions_classe_base(classe, annee):
    return (
        Inscription.objects.filter(classe=classe, annee_academique=annee)
        .eligibles_listes()
        .select_related('etudiant')
        .order_by('etudiant__numero_etudiant')
    )


def ecs_rattrapage_pour_classe(classe, session, annee, ecs_base):
    """EC avec au moins un étudiant convoqué au rattrapage (examen < 10/10)."""
    if session.numero != 2:
        return ecs_base
    s1 = session_principale(session)
    if not s1:
        return ecs_base
    promotion = classe.promotion
    ec_ids = []
    for ec in ecs_base:
        if etudiants_ajournes_ec_ids(ec, s1, promotion, annee):
            ec_ids.append(ec.pk)
    if not ec_ids:
        return ecs_base.none()
    return ecs_base.filter(pk__in=ec_ids)


def _type_rattrapage():
    type_eval, _ = TypeEvaluation.objects.get_or_create(
        code='RATT',
        defaults={
            'nom': 'Rattrapage (examen)',
            'coefficient': Decimal('1.00'),
            'note_max': Decimal('10.00'),
            'ordre': 4,
            'active': True,
        },
    )
    return type_eval


@transaction.atomic
def prepare_rattrapage_session(session_principale_obj, promotion):
    """
    Ouvre la session de rattrapage : crée S2 et les évaluations RATT pour les EC
    où au moins un étudiant a une note d'examen < 10/10.
    La session principale doit être verrouillée.
    """
    if session_principale_obj.numero != 1:
        raise SessionWorkflowError('Le rattrapage se prépare depuis la session principale (n° 1).')
    if not session_principale_obj.verrouillee:
        raise SessionWorkflowError('Verrouillez d\'abord la session principale.')

    session_ratt, created = Session.objects.get_or_create(
        semestre=session_principale_obj.semestre,
        numero=2,
        annee_academique=session_principale_obj.annee_academique,
        defaults={
            'code': f'{session_principale_obj.semestre.code}-S2'[:50],
            'nom': f'Rattrapage — {session_principale_obj.semestre.nom}',
            'date_debut': session_principale_obj.date_fin + timedelta(days=1),
            'date_fin': session_principale_obj.date_fin + timedelta(days=15),
            'active': True,
            'verrouillee': False,
            'deliberation_faite': False,
        },
    )
    if session_ratt.verrouillee:
        raise SessionWorkflowError('La session de rattrapage est déjà verrouillée.')

    type_ratt = _type_rattrapage()
    evals_crees = 0
    ecs_rattrapage = set()

    ecs_qs = ElementConstitutif.objects.filter(
        ue__semestre=session_principale_obj.semestre,
        active=True,
    )
    if getattr(promotion, 'filiere_id', None):
        ecs_qs = ecs_qs.filter(ue__filiere_id=promotion.filiere_id)

    for inscription in _inscriptions_promotion(promotion):
        etudiant = inscription.etudiant
        for ec in ecs_qs:
            evaluations = _evaluations_exam_session_principale(ec, session_principale_obj)
            note_exam = note_exam_etudiant_sur_10(etudiant, evaluations)
            if not etudiant_convoque_rattrapage(note_exam):
                continue
            ecs_rattrapage.add(ec)
            _, ev_created = Evaluation.objects.get_or_create(
                ec=ec,
                session=session_ratt,
                type_evaluation=type_ratt,
                defaults={
                    'annee_academique': session_ratt.annee_academique,
                    'code': Evaluation.build_code(ec, session_ratt, type_ratt),
                    'nom': Evaluation.build_nom(type_ratt, ec, session_ratt),
                    'date_evaluation': session_ratt.date_debut,
                    'coefficient': type_ratt.coefficient,
                    'note_max': type_ratt.note_max,
                    'active': True,
                },
            )
            if ev_created:
                evals_crees += 1

    return {
        'session_rattrapage': session_ratt,
        'created': created,
        'evaluations_crees': evals_crees,
        'ecs_ajournes': len(ecs_rattrapage),
    }


def verrouiller_session(session):
    """Verrouille une session (fin de saisie)."""
    if session.verrouillee:
        raise SessionWorkflowError('Cette session est déjà verrouillée.')
    if session.numero == 2:
        s1 = session_principale(session)
        if not s1 or not s1.verrouillee:
            raise SessionWorkflowError('Verrouillez d\'abord la session principale.')
    session.verrouillee = True
    session.save(update_fields=['verrouillee', 'updated_at'])
    return session


def deverrouiller_session(session):
    """Déverrouille une session si la délibération n'est pas faite."""
    if session.deliberation_faite:
        raise SessionWorkflowError('Impossible de déverrouiller : délibération déjà effectuée.')
    if session.numero == 1:
        s2 = session_rattrapage(session)
        if s2 and (s2.verrouillee or s2.deliberation_faite):
            raise SessionWorkflowError('Déverrouillez d\'abord la session de rattrapage.')
    session.verrouillee = False
    session.save(update_fields=['verrouillee', 'updated_at'])
    return session


def peut_deliberer(session, promotion):
    """
    Vérifie les prérequis de délibération semestrielle.
    Retourne (ok: bool, message: str).
    """
    if not session.verrouillee:
        return False, 'La session doit être verrouillée avant la délibération.'
    if session.numero == 1:
        s2 = session_rattrapage(session)
        if s2 and s2.active and not s2.deliberation_faite:
            if not s2.verrouillee:
                return False, (
                    'Une session de rattrapage est ouverte : verrouillez-la '
                    'ou finalisez le rattrapage avant de délibérer sur la session principale.'
                )
    if session.numero == 2:
        s1 = session_principale(session)
        if not s1 or not s1.verrouillee:
            return False, 'La session principale doit être verrouillée.'
    if session.deliberation_faite:
        return False, 'La délibération a déjà été effectuée pour cette session.'
    return True, ''


def workflow_etat_session(session):
    """Libellés d'état pour l'interface."""
    s1 = session_principale(session) if session.numero == 2 else session
    s2 = session_rattrapage(session) if session.numero == 1 else (
        session if session.numero == 2 else None
    )
    return {
        'session': session,
        'principale': s1,
        'rattrapage': s2,
        'peut_verrouiller': not session.verrouillee and not session.deliberation_faite,
        'peut_deverrouiller': session.verrouillee and not session.deliberation_faite,
        'peut_preparer_rattrapage': (
            session.numero == 1
            and session.verrouillee
            and not session.deliberation_faite
            and (not s2 or not s2.verrouillee)
        ),
    }
