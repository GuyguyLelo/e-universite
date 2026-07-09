"""
Calcul des notes EC : moyenne des travaux journaliers (TJ) et de l'examen du semestre.

TJ et examen (y compris rattrapage) sont saisis sur /10 ; la moyenne est exprimée sur /20.
Une note non saisie n'entre pas dans le calcul (affichage « — »).
Le rattrapage remplace l'examen lorsque la note d'examen est strictement inférieure à 10/10.
"""
from decimal import Decimal

from evaluations.models import Note

BAREME_TJ_EXAM = Decimal('10.00')
BAREME_FINAL = Decimal('20.00')
SEUIL_EXAM_SANS_RATTRAPAGE = Decimal('10.00')
TIRET_COTATION = '—'


def est_type_tj(type_evaluation) -> bool:
    """Travaux journaliers (CC historique inclus pour compatibilité)."""
    code = (type_evaluation.code or '').upper()
    return code in {'TJ', 'TP', 'CC', 'TJS'} or code.startswith('TJ')


def est_type_exam(type_evaluation) -> bool:
    """Examen du semestre (session principale)."""
    code = (type_evaluation.code or '').upper()
    return code in {'EXAM', 'EXAMEN', 'EX'}


def est_type_rattrapage(type_evaluation) -> bool:
    """Rattrapage : considéré comme un examen sur /10."""
    code = (type_evaluation.code or '').upper()
    return code in {'RATT', 'RATTRAPAGE'}


def est_type_exam_ou_rattrapage(type_evaluation) -> bool:
    return est_type_exam(type_evaluation) or est_type_rattrapage(type_evaluation)


def _note_sur_bareme(note_obj, evaluation) -> Decimal:
    return note_obj.note_sur or evaluation.note_max or BAREME_TJ_EXAM


def _ramener_sur_10(note: Decimal, note_sur: Decimal) -> Decimal:
    if note_sur <= 0:
        return Decimal('0.00')
    if note_sur == BAREME_TJ_EXAM:
        return note
    return (note / note_sur) * BAREME_TJ_EXAM


def _note_tj_exam_sur_10(note_obj, evaluation) -> Decimal:
    """Note TJ, examen ou rattrapage ramenée sur /10."""
    return _ramener_sur_10(note_obj.note or Decimal('0.00'), _note_sur_bareme(note_obj, evaluation))


def _note_finale_sur_20(note_obj) -> Decimal:
    return note_obj.note_finale or Decimal('0.00')


def _lecture_cote_sur_10(etudiant, evaluation) -> tuple[str, Decimal | None]:
    """
    Retourne le statut de saisie et la valeur sur /10.

    - manquante : pas de note saisie
    - absence_justifiee : exclue du calcul
    - saisie : note ou 0 (absence non justifiée)
    """
    try:
        note_obj = Note.objects.get(etudiant=etudiant, evaluation=evaluation)
    except Note.DoesNotExist:
        return 'manquante', None

    if note_obj.absent and note_obj.justifie:
        return 'absence_justifiee', None
    if note_obj.absent and not note_obj.justifie:
        return 'saisie', Decimal('0.00')
    if note_obj.note is None:
        return 'manquante', None
    return 'saisie', _note_tj_exam_sur_10(note_obj, evaluation)


def _moyenne_sur_10(notes_sur_10) -> Decimal | None:
    if not notes_sur_10:
        return None
    return sum(notes_sur_10, Decimal('0.00')) / len(notes_sur_10)


def _moyenne_bloc_sur_10(etudiant, evaluations, *, type_predicate) -> tuple[Decimal | None, bool]:
    """
    Moyenne /10 d'un bloc (TJ, examen, rattrapage).
    Retourne (valeur, bloc_configure) ; valeur None si note manquante ou bloc vide.
    """
    evals_cibles = [
        evaluation
        for evaluation in evaluations
        if type_predicate(evaluation.type_evaluation)
    ]
    if not evals_cibles:
        return None, False

    valeurs = []
    for evaluation in evals_cibles:
        statut, valeur = _lecture_cote_sur_10(etudiant, evaluation)
        if statut in {'manquante', 'absence_justifiee'}:
            return None, True
        valeurs.append(valeur)

    return _moyenne_sur_10(valeurs), True


def _moyenne_sur_20_depuis_bloc_tj_exam(note_tj_sur_10, note_exam_sur_10) -> Decimal | None:
    """Moyenne sur /20 uniquement si TJ et examen sont saisis."""
    if note_tj_sur_10 is None or note_exam_sur_10 is None:
        return None
    moyenne_sur_10 = (note_tj_sur_10 + note_exam_sur_10) / 2
    return (moyenne_sur_10 * (BAREME_FINAL / BAREME_TJ_EXAM)).quantize(Decimal('0.01'))


def _evaluations_ont_tj_exam(evaluations) -> bool:
    has_tj = any(est_type_tj(e.type_evaluation) for e in evaluations)
    has_exam = any(
        est_type_exam(e.type_evaluation) or est_type_rattrapage(e.type_evaluation)
        for e in evaluations
    )
    return has_tj and has_exam


def note_exam_etudiant_sur_10(etudiant, evaluations) -> Decimal | None:
    """Note d'examen (session principale) sur /10, hors rattrapage."""
    valeur, _ = _moyenne_bloc_sur_10(etudiant, evaluations, type_predicate=est_type_exam)
    return valeur


def note_rattrapage_etudiant_sur_10(etudiant, evaluations) -> Decimal | None:
    """Note de rattrapage sur /10."""
    valeur, _ = _moyenne_bloc_sur_10(etudiant, evaluations, type_predicate=est_type_rattrapage)
    return valeur


def note_exam_retenue_sur_10(note_exam_s1: Decimal | None, note_ratt_s2: Decimal | None) -> Decimal | None:
    """
    Examen retenu sur /10 pour affichage et moyenne.
    Si l'examen initial est >= 10/10, il est conservé ; sinon le rattrapage le remplace.
    """
    if note_exam_s1 is not None and note_exam_s1 >= SEUIL_EXAM_SANS_RATTRAPAGE:
        return note_exam_s1
    if note_exam_s1 is not None and note_ratt_s2 is not None:
        return note_ratt_s2
    return note_exam_s1 if note_exam_s1 is not None else note_ratt_s2


def etudiant_convoque_rattrapage(note_exam_s1: Decimal | None) -> bool:
    """Rattrapage uniquement si l'examen est saisi et strictement inférieur à 10/10."""
    if note_exam_s1 is None:
        return False
    return note_exam_s1 < SEUIL_EXAM_SANS_RATTRAPAGE


def _moyenne_tj_sur_10(etudiant, evaluations):
    return _moyenne_bloc_sur_10(etudiant, evaluations, type_predicate=est_type_tj)


def _exam_et_rattrapage_sur_10(etudiant, evaluations_s1, evaluations_s2=None):
    note_exam_s1, _ = _moyenne_bloc_sur_10(
        etudiant,
        evaluations_s1,
        type_predicate=est_type_exam,
    )
    note_ratt = (
        note_rattrapage_etudiant_sur_10(etudiant, evaluations_s2)
        if evaluations_s2
        else None
    )
    return note_exam_s1, note_ratt


def calculer_note_ec(etudiant, evaluations) -> Decimal | None:
    """
    Note finale EC pour une seule session.
    TJ + examen requis et saisis ; sinon None.
    """
    evaluations = list(evaluations)
    if not evaluations:
        return None

    note_tj, has_tj = _moyenne_tj_sur_10(etudiant, evaluations)
    note_exam_s1, has_exam = _moyenne_bloc_sur_10(
        etudiant,
        evaluations,
        type_predicate=est_type_exam,
    )
    note_ratt, has_ratt = _moyenne_bloc_sur_10(
        etudiant,
        evaluations,
        type_predicate=est_type_rattrapage,
    )

    if has_tj and (has_exam or has_ratt):
        note_exam = note_exam_retenue_sur_10(note_exam_s1, note_ratt)
        return _moyenne_sur_20_depuis_bloc_tj_exam(note_tj, note_exam)

    autres = []
    for evaluation in evaluations:
        type_eval = evaluation.type_evaluation
        if est_type_tj(type_eval) or est_type_exam_ou_rattrapage(type_eval):
            continue
        statut, valeur = _lecture_cote_sur_10(etudiant, evaluation)
        if statut in {'manquante', 'absence_justifiee'}:
            continue
        autres.append((valeur * (BAREME_FINAL / BAREME_TJ_EXAM), evaluation.coefficient))

    if autres:
        total_pondere = Decimal('0.00')
        total_coefficients = Decimal('0.00')
        for note_val, coef in autres:
            total_pondere += note_val * coef
            total_coefficients += coef
        if total_coefficients > 0:
            return (total_pondere / total_coefficients).quantize(Decimal('0.01'))

    return None


def calculer_note_ec_combine_sessions(etudiant, evaluations_s1, evaluations_s2=None) -> Decimal | None:
    """Note EC après session principale et éventuel rattrapage."""
    evaluations_s1 = list(evaluations_s1 or [])
    note_tj, has_tj = _moyenne_tj_sur_10(etudiant, evaluations_s1)
    note_exam_s1, note_ratt = _exam_et_rattrapage_sur_10(
        etudiant,
        evaluations_s1,
        evaluations_s2,
    )
    note_exam = note_exam_retenue_sur_10(note_exam_s1, note_ratt)

    if has_tj and (note_exam_s1 is not None or note_ratt is not None):
        return _moyenne_sur_20_depuis_bloc_tj_exam(note_tj, note_exam)

    return calculer_note_ec(
        etudiant,
        evaluations_s1 + list(evaluations_s2 or []),
    )


def resume_cotation_ec_etudiant(etudiant, evaluations_s1, evaluations_s2=None) -> dict:
    """Résumé fiche de cotation : TJ/10, EXAM/10 (retenu), MOY/20."""
    evaluations_s1 = list(evaluations_s1 or [])
    note_tj, _ = _moyenne_tj_sur_10(etudiant, evaluations_s1)
    note_exam_s1, note_ratt = _exam_et_rattrapage_sur_10(
        etudiant,
        evaluations_s1,
        evaluations_s2,
    )
    note_exam = note_exam_retenue_sur_10(note_exam_s1, note_ratt)

    if evaluations_s2:
        moy = calculer_note_ec_combine_sessions(etudiant, evaluations_s1, evaluations_s2)
    else:
        moy = calculer_note_ec(etudiant, evaluations_s1)

    return {
        'tj_sur_10': note_tj,
        'exam_sur_10': note_exam,
        'moy_sur_20': moy,
    }


def formater_cote_affichage(valeur) -> str:
    """Formate une note pour PDF / grille ; None → tiret."""
    if valeur is None:
        return TIRET_COTATION
    return format(valeur.quantize(Decimal('0.01')), 'f').rstrip('0').rstrip('.')
