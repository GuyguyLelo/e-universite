"""Génération et validation des matricules étudiants."""

from collections import defaultdict

from academics.models import AnneeAcademique

FILIERE_MATRICULE_SUFFIX = {
    'CSI': 'C',
    'RX': 'R',
}

PREMASTER_FILIERE_CODE = 'TC'

MATRICULE_REGEX = r'^(\d{7}|\d{4}[RC]\d{3})$'
MATRICULE_HELP = (
    "Pre-Master / Master RX : année de début + n° à 3 chiffres (ex. 2024001, 2025001). "
    "Master CSI : année de fin + C + n° à 3 chiffres (ex. 2026C001)."
)


def matricule_year_default(annee=None):
    """Année affichée dans le matricule (ex. 2026 pour 2025-2026)."""
    annee = annee or AnneeAcademique.get_active()
    if not annee:
        return None
    return annee.annee_fin


def format_matricule(year, suffix, order):
    return f"{int(year)}{suffix}{int(order):03d}"


def format_matricule_premaster(annee_debut, order):
    """Année de début + n° séquentiel (ex. 2024001) — Pre-Master ou Master RX."""
    return format_matricule_annee_debut(annee_debut, order)


def format_matricule_annee_debut(annee_debut, order):
    return f"{int(annee_debut)}{int(order):03d}"


def suffix_for_filiere(filiere_code):
    suffix = FILIERE_MATRICULE_SUFFIX.get(filiere_code)
    if not suffix:
        raise ValueError(f"Filière non prise en charge pour le matricule : {filiere_code}")
    return suffix


def build_matricule_assignments_from_lists(annee, csi_rows, rx_rows, find_student):
    """
    Numérotation selon l'ordre des listes officielles (Conception / Réseaux).
    find_student(row) -> Student | None
    """
    assignments = []
    assigned = set()
    year_fin = annee.annee_fin
    year_debut = annee.annee_debut

    for idx, row in enumerate(csi_rows, start=1):
        student = find_student(row)
        if student and student.pk not in assigned:
            assignments.append((student, format_matricule(year_fin, 'C', idx)))
            assigned.add(student.pk)

    for idx, row in enumerate(rx_rows, start=1):
        student = find_student(row)
        if student and student.pk not in assigned:
            assignments.append((student, format_matricule_annee_debut(year_debut, idx)))
            assigned.add(student.pk)

    return assignments


def build_matricule_assignments(annee, year=None):
    """
    Retourne [(student, nouveau_matricule), …] pour l'année académique donnée.
    Suffixe selon la filière d'inscription (CSI → C, RX → R), ordre alphabétique.
    """
    from students.models import Inscription

    year = year or matricule_year_default(annee)
    if not year:
        raise ValueError("Année de matricule introuvable.")

    inscriptions = (
        Inscription.objects.filter(
            annee_academique=annee,
            classe__isnull=False,
            classe__promotion__filiere__isnull=False,
        )
        .select_related('etudiant', 'classe__promotion__filiere')
        .order_by('classe__promotion__filiere__code', 'etudiant__nom', 'etudiant__prenom')
    )

    by_filiere = defaultdict(list)
    seen = set()
    for ins in inscriptions:
        filiere_code = ins.classe.promotion.filiere.code
        if filiere_code not in FILIERE_MATRICULE_SUFFIX:
            continue
        if ins.etudiant_id in seen:
            continue
        seen.add(ins.etudiant_id)
        by_filiere[filiere_code].append(ins.etudiant)

    assignments = []
    for filiere_code in sorted(FILIERE_MATRICULE_SUFFIX.keys()):
        students = by_filiere.get(filiere_code, [])
        students.sort(key=lambda s: (s.nom.upper(), s.prenom.upper()))
        if filiere_code == 'RX':
            for order, student in enumerate(students, start=1):
                assignments.append((
                    student,
                    format_matricule_annee_debut(annee.annee_debut, order),
                ))
        else:
            suffix = FILIERE_MATRICULE_SUFFIX[filiere_code]
            for order, student in enumerate(students, start=1):
                assignments.append((student, format_matricule(year, suffix, order)))

    return assignments


def build_master_rx_matricule_assignments(annee, students=None):
    """
    Retourne [(student, nouveau_matricule), …] pour les inscriptions Master RX.
    students : liste optionnelle déjà ordonnée ; sinon tri alphabétique nom/prénom.
    """
    from students.models import Inscription

    if students is None:
        inscriptions = (
            Inscription.objects.filter(
                annee_academique=annee,
                classe__promotion__filiere__code='RX',
            )
            .select_related('etudiant')
            .order_by('etudiant__nom', 'etudiant__prenom')
        )
        students = []
        seen = set()
        for ins in inscriptions:
            if ins.etudiant_id not in seen:
                seen.add(ins.etudiant_id)
                students.append(ins.etudiant)

    year = annee.annee_debut
    return [
        (student, format_matricule_annee_debut(year, order))
        for order, student in enumerate(students, start=1)
    ]


def build_premaster_matricule_assignments(annee, students=None, order_key=None):
    """
    Retourne [(student, nouveau_matricule), …] pour les inscriptions tronc commun (TC).
    students : liste optionnelle déjà ordonnée ; sinon tri alphabétique nom/prénom.
    """
    from students.models import Inscription

    if students is None:
        inscriptions = (
            Inscription.objects.filter(
                annee_academique=annee,
                classe__promotion__filiere__code=PREMASTER_FILIERE_CODE,
            )
            .select_related('etudiant')
            .order_by('etudiant__nom', 'etudiant__prenom')
        )
        students = []
        seen = set()
        for ins in inscriptions:
            if ins.etudiant_id not in seen:
                seen.add(ins.etudiant_id)
                students.append(ins.etudiant)
        if order_key:
            students.sort(key=order_key)

    year = annee.annee_debut
    return [
        (student, format_matricule_premaster(year, order))
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
