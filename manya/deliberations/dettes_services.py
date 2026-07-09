"""
Dettes académiques : étudiants passés en promotion supérieure (ex. M1 → M2)
avec des EC non validés (< 10/20) de la promotion précédente.
"""
from decimal import Decimal

from django.db.models import Q

from academics.models import AnneeAcademique, Promotion, Semestre
from deliberations.annual_services import session_finale_semestre
from deliberations.services import DeliberationEngine
from evaluations.models import Session
from students.models import Inscription, Student

SEUIL_VALIDATION_EC = Decimal('10.00')


def semestres_pour_promotion(promotion):
    """Semestres LMD couverts par une promotion (ordre N → S(2N-1) et S(2N))."""
    numeros = (2 * promotion.ordre - 1, 2 * promotion.ordre)
    return Semestre.objects.filter(numero__in=numeros, active=True).order_by('numero')


def promotion_precedente(promotion):
    if not promotion or promotion.ordre <= 1:
        return None
    return Promotion.objects.filter(
        filiere=promotion.filiere,
        ordre=promotion.ordre - 1,
        active=True,
    ).first()


def annee_academique_precedente(annee_academique):
    if not annee_academique:
        return None
    return AnneeAcademique.objects.filter(
        annee_debut=annee_academique.annee_debut - 1,
    ).first()


def session_pour_calcul_dettes(semestre, promotion, annee_academique):
    """Session retenue pour le calcul (délibération finalisée, rattrapage ou principale)."""
    session = session_finale_semestre(semestre, promotion, annee_academique)
    if session:
        return session
    if not annee_academique:
        return None
    base = {'semestre': semestre, 'annee_academique': annee_academique, 'active': True}
    return (
        Session.objects.filter(numero=2, **base).first()
        or Session.objects.filter(numero=1, **base).first()
    )


def ecs_en_dette_etudiant(engine: DeliberationEngine, etudiant: Student) -> list[dict]:
    """EC du semestre dont la note finale est strictement inférieure à 10/20."""
    dettes = []
    for ec in engine._ecs_semestre_qs():
        note = engine._note_ec_effective(etudiant, ec)
        if note is None or note >= SEUIL_VALIDATION_EC:
            continue
        dettes.append({
            'ec': ec,
            'ue': ec.ue,
            'note': note,
            'credits': ec.credits_ects,
        })
    dettes.sort(key=lambda item: (item['ue'].ordre, item['ue'].code, item['ec'].ordre, item['ec'].code))
    return dettes


def dettes_promotion_etudiant(etudiant, promotion_dette, annee_dette) -> list[dict]:
    """Tous les EC en dette sur les semestres d'une promotion (année de référence)."""
    dettes = []
    for semestre in semestres_pour_promotion(promotion_dette):
        session = session_pour_calcul_dettes(semestre, promotion_dette, annee_dette)
        if not session:
            continue
        engine = DeliberationEngine(session, promotion_dette)
        for item in ecs_en_dette_etudiant(engine, etudiant):
            dettes.append({
                **item,
                'semestre': semestre,
                'annee_dette': annee_dette,
                'promotion_dette': promotion_dette,
            })
    return dettes


def inscription_passage_promotion(etudiant, promotion_actuelle, annee_actuelle):
    """
    Vérifie un passage de promotion (ex. M1 → M2) : inscription N-1 sur la promotion précédente.
    Retourne (inscription_prec, promotion_prec, annee_prec) ou (None, None, None).
    """
    promotion_prec = promotion_precedente(promotion_actuelle)
    annee_prec = annee_academique_precedente(annee_actuelle)
    if not promotion_prec or not annee_prec:
        return None, None, None

    inscription_prec = (
        Inscription.objects.filter(
            etudiant=etudiant,
            annee_academique=annee_prec,
            classe__promotion=promotion_prec,
        )
        .eligibles_listes()
        .select_related('classe', 'classe__promotion')
        .first()
    )
    if not inscription_prec:
        return None, None, None
    return inscription_prec, promotion_prec, annee_prec


def lister_passages_avec_dettes(
    *,
    annee_academique,
    filiere=None,
    promotion=None,
    classe=None,
    q=None,
) -> list[dict]:
    """
    Étudiants inscrits en promotion supérieure (ordre ≥ 2) ayant des EC en dette
    sur la promotion précédente (année N-1).
    """
    inscriptions = (
        Inscription.objects.filter(
            annee_academique=annee_academique,
            classe__promotion__ordre__gte=2,
        )
        .eligibles_listes()
        .select_related(
            'etudiant',
            'classe',
            'classe__promotion',
            'classe__promotion__filiere',
        )
        .order_by(
            'classe__promotion__filiere__code',
            'classe__promotion__ordre',
            'classe__code',
            'etudiant__nom',
            'etudiant__prenom',
        )
    )
    if filiere:
        inscriptions = inscriptions.filter(classe__promotion__filiere=filiere)
    if promotion:
        inscriptions = inscriptions.filter(classe__promotion=promotion)
    if classe:
        inscriptions = inscriptions.filter(classe=classe)
    if q:
        terme = q.strip()
        if terme:
            inscriptions = inscriptions.filter(
                Q(etudiant__numero_etudiant__icontains=terme)
                | Q(etudiant__nom__icontains=terme)
                | Q(etudiant__prenom__icontains=terme)
            )

    lignes = []
    for inscription in inscriptions:
        promotion_actuelle = inscription.classe.promotion
        _, promotion_prec, annee_prec = inscription_passage_promotion(
            inscription.etudiant,
            promotion_actuelle,
            annee_academique,
        )
        if not promotion_prec:
            continue

        dettes = dettes_promotion_etudiant(
            inscription.etudiant,
            promotion_prec,
            annee_prec,
        )
        if not dettes:
            continue

        lignes.append({
            'inscription': inscription,
            'etudiant': inscription.etudiant,
            'classe': inscription.classe,
            'promotion_actuelle': promotion_actuelle,
            'promotion_dette': promotion_prec,
            'annee_dette': annee_prec,
            'dettes': dettes,
            'nb_dettes': len(dettes),
        })

    return lignes
