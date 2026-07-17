"""Génération et validation des matricules étudiants."""

from academics.models import AnneeAcademique

MATRICULE_REGEX = r'^(\d{8}|\d{7}|\d{4}[RC]\d{3})$'
MATRICULE_HELP = "Année + n° d'ordre sur 4 chiffres (ex. 20260001), sans distinction de filière."


def matricule_year_default(annee=None):
    """Année affichée dans le matricule (ex. 2026 pour 2025-2026)."""
    annee = annee or AnneeAcademique.get_active()
    if not annee:
        return None
    return annee.annee_fin


def format_matricule(year, order):
    """Matricule unifié : année + n° séquentiel (ex. 20260001)."""
    return f"{int(year)}{int(order):04d}"


def format_matricule_premaster(annee_debut, order):
    """Alias rétrocompatibilité — utilise l'année passée."""
    return format_matricule(annee_debut, order)


def format_matricule_annee_debut(annee_debut, order):
    """Alias rétrocompatibilité — utilise l'année passée."""
    return format_matricule(annee_debut, order)


def _collect_students_for_annee(annee, *, filiere_code=None, students=None, order_key=None):
    from students.models import Inscription

    if students is not None:
        result = list(students)
    else:
        qs = Inscription.objects.filter(
            annee_academique=annee,
            classe__isnull=False,
        )
        if filiere_code:
            qs = qs.filter(classe__promotion__filiere__code=filiere_code)
        inscriptions = qs.select_related('etudiant').order_by(
            'etudiant__nom', 'etudiant__prenom',
        )
        result = []
        seen = set()
        for ins in inscriptions:
            if ins.etudiant_id not in seen:
                seen.add(ins.etudiant_id)
                result.append(ins.etudiant)

    if order_key:
        result.sort(key=order_key)
    else:
        result.sort(key=lambda s: (s.nom.upper(), s.prenom.upper()))
    return result


def build_matricule_assignments_from_lists(annee, csi_rows, rx_rows, find_student):
    """
    Numérotation selon l'ordre des listes officielles (CSI puis RX).
    find_student(row) -> Student | None
    """
    assignments = []
    assigned = set()
    year = matricule_year_default(annee)
    order = 0

    for row in list(csi_rows) + list(rx_rows):
        student = find_student(row)
        if student and student.pk not in assigned:
            order += 1
            assignments.append((student, format_matricule(year, order)))
            assigned.add(student.pk)

    return assignments


def build_matricule_assignments(annee, year=None, students=None, order_key=None):
    """
    Retourne [(student, nouveau_matricule), …] pour l'année académique donnée.
    Numérotation unique par année, ordre alphabétique nom/prénom.
    """
    year = year or matricule_year_default(annee)
    if not year:
        raise ValueError("Année de matricule introuvable.")

    students = _collect_students_for_annee(
        annee, students=students, order_key=order_key,
    )
    return [
        (student, format_matricule(year, order))
        for order, student in enumerate(students, start=1)
    ]


def build_master_rx_matricule_assignments(annee, students=None):
    """Retourne les matricules pour les inscriptions Master RX (format unifié)."""
    year = matricule_year_default(annee)
    students = _collect_students_for_annee(
        annee, filiere_code='RX', students=students,
    )
    return [
        (student, format_matricule(year, order))
        for order, student in enumerate(students, start=1)
    ]


def build_premaster_matricule_assignments(annee, students=None, order_key=None):
    """Retourne les matricules pour les inscriptions tronc commun (format unifié)."""
    year = matricule_year_default(annee)
    students = _collect_students_for_annee(
        annee,
        filiere_code='TC',
        students=students,
        order_key=order_key,
    )
    return [
        (student, format_matricule(year, order))
        for order, student in enumerate(students, start=1)
    ]


def apply_matricule_assignments(assignments, update_email=False):
    """Applique les matricules (phase temporaire pour éviter les doublons uniques)."""
    from students.models import Student

    if not assignments:
        return 0

    for i, (student, _new) in enumerate(assignments):
        Student.objects.filter(pk=student.pk).update(numero_etudiant=f"TMPMAT{i:05d}")

    updated = 0
    for student, new_numero in assignments:
        fields = {'numero_etudiant': new_numero}
        if update_email:
            fields['email'] = f"{new_numero.lower()}@student.ecore.local"
        Student.objects.filter(pk=student.pk).update(**fields)
        updated += 1

    return updated
