"""
Production des décisions du jury selon le barème institutionnel :
Admis, Admis par compensation, Défaillant, Ajourné, Admis avec dettes.
"""
from decimal import Decimal

from evaluations.calcul_notes import (
    _lecture_cote_sur_10,
    est_type_exam,
    est_type_rattrapage,
    est_type_tj,
)
from evaluations.models import Evaluation, Note


def _evaluation_obligatoire(evaluation) -> bool:
    type_eval = evaluation.type_evaluation
    return (
        est_type_tj(type_eval)
        or est_type_exam(type_eval)
        or est_type_rattrapage(type_eval)
    )


def _sessions_pour_controle(engine):
    if getattr(engine, 'mode_final', False) and getattr(engine, 'session_principale', None):
        return [engine.session_principale, engine.session]
    return [engine.session]


def etudiant_defaillant(engine, etudiant) -> bool:
    """
    Défaillant : absence non justifiée ou note manquante sur une évaluation obligatoire.
    """
    filiere_id = getattr(engine, 'filiere_id', None)

    for session in _sessions_pour_controle(engine):
        if not session:
            continue
        evaluations = Evaluation.objects.filter(session=session, active=True).select_related(
            'type_evaluation', 'ec__ue',
        )
        if filiere_id:
            evaluations = evaluations.filter(ec__ue__filiere_id=filiere_id)

        for evaluation in evaluations:
            if not _evaluation_obligatoire(evaluation):
                continue
            statut, _ = _lecture_cote_sur_10(etudiant, evaluation)
            if statut == 'manquante':
                return True
            try:
                note_obj = Note.objects.get(etudiant=etudiant, evaluation=evaluation)
            except Note.DoesNotExist:
                continue
            if note_obj.absent and not note_obj.justifie:
                return True
    return False


def ecs_notes_eliminatoires(resultat: dict) -> list:
    """EC dont la note finale est strictement inférieure au seuil éliminatoire."""
    eliminatoires = []
    for data in resultat.get('notes_ec', {}).values():
        if data.get('est_eliminatoire'):
            eliminatoires.append(data['ec'])
    return eliminatoires


def analyser_validation_ues(resultat: dict, seuil: Decimal) -> tuple[list, list, list]:
    """
    Classe les UE : validées directement (≥ seuil), par compensation, ou non validées.
    """
    directes = []
    compensees = []
    non_validees = []

    for data in resultat.get('notes_ue', {}).values():
        note = data.get('note')
        ue = data['ue']
        valide = data.get('valide', False)
        valide_directe = note is not None and note >= seuil

        if valide_directe:
            directes.append(ue)
        elif valide:
            compensees.append(ue)
        else:
            non_validees.append(ue)

    return directes, compensees, non_validees


def analyser_validation_ues_annuelle(r1: dict, r2: dict, seuil: Decimal) -> tuple[list, list, list]:
    """Agrège l'analyse UE sur deux semestres."""
    d1, c1, n1 = analyser_validation_ues(r1, seuil)
    d2, c2, n2 = analyser_validation_ues(r2, seuil)
    return d1 + d2, c1 + c2, n1 + n2


def _seuil_passage_dettes(seuil_credits_minimum: int, credits_totaux: Decimal, multiplicateur: int) -> Decimal:
    return min(
        Decimal(str(seuil_credits_minimum * multiplicateur)),
        credits_totaux,
    )


def produire_decision_semestre(
    engine,
    etudiant,
    resultat: dict,
) -> str:
    """
    Décision semestrielle.
    - Défaillant : absences / notes manquantes sur évaluations obligatoires
    - Ajourné : moyenne < 10 ou crédits insuffisants sans passage avec dettes
    - Admis : moyenne ≥ 10, toutes les UE ≥ 10 (validation directe)
    - Admis par compensation : moyenne ≥ 10, UE compensées mais toutes validées
    - Admis avec dettes : moyenne ≥ 10, UE non validées, passage autorisé
    """
    parametres = engine.parametres
    seuil = parametres.seuil_validation
    moyenne = resultat['moyenne_semestre']
    credits_obtenus = resultat['credits_obtenus']
    credits_totaux = resultat['credits_totaux']

    if etudiant_defaillant(engine, etudiant):
        return 'defaillant'

    if moyenne is None:
        return 'ajourne'

    if not engine._note_depasse_seuil(moyenne, seuil):
        return 'ajourne'

    _, compensees, non_validees = analyser_validation_ues(resultat, seuil)
    eliminatoires = ecs_notes_eliminatoires(resultat)

    if non_validees:
        seuil_min = _seuil_passage_dettes(
            parametres.seuil_credits_minimum, credits_totaux, 1,
        )
        if (
            parametres.passage_avec_dettes
            and credits_obtenus >= seuil_min
            and credits_obtenus < credits_totaux
        ):
            return 'admis_avec_dettes'
        return 'ajourne'

    if compensees or eliminatoires:
        return 'admis_compensation'
    return 'admis'


def produire_decision_agregee(
    engines,
    etudiant,
    resultats: list[dict],
    moyenne_globale,
    credits_obtenus: Decimal,
    credits_totaux: Decimal,
    multiplicateur_seuil: int,
) -> str:
    """
    Décision annuelle ou cycle : même barème sur la moyenne agrégée et l'ensemble des UE.
    """
    if not engines:
        return 'ajourne'

    parametres = engines[0].parametres
    seuil = parametres.seuil_validation
    note_ok = engines[0]._note_depasse_seuil

    for engine in engines:
        if etudiant_defaillant(engine, etudiant):
            return 'defaillant'

    if moyenne_globale is None:
        return 'ajourne'

    if not note_ok(moyenne_globale, seuil):
        return 'ajourne'

    compensees = []
    non_validees = []
    eliminatoires = []
    for resultat in resultats:
        _, comp, non_val = analyser_validation_ues(resultat, seuil)
        compensees.extend(comp)
        non_validees.extend(non_val)
        eliminatoires.extend(ecs_notes_eliminatoires(resultat))

    if non_validees:
        seuil_min = _seuil_passage_dettes(
            parametres.seuil_credits_minimum, credits_totaux, multiplicateur_seuil,
        )
        if (
            parametres.passage_avec_dettes
            and credits_obtenus >= seuil_min
            and credits_obtenus < credits_totaux
        ):
            return 'admis_avec_dettes'
        return 'ajourne'

    if compensees or eliminatoires:
        return 'admis_compensation'
    return 'admis'
