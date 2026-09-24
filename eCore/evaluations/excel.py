"""Export / import Excel — fiche de cotation (TJ/10, EXAM/10, MOY/20)."""
from __future__ import annotations

import re
import secrets
import unicodedata
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from evaluations.calcul_notes import (
    BAREME_TJ_EXAM,
    _lecture_cote_sur_10,
    _moyenne_sur_20_depuis_bloc_tj_exam,
    est_type_exam,
    est_type_rattrapage,
    est_type_tj,
)
from evaluations.models import Evaluation
from evaluations.pdf import libelle_enseignant_ec
from config.pdf_entete import institution_nom_majuscules
from evaluations.session_workflow import session_principale


INFO_START_ROW = 3
DEFAULT_DATA_START_ROW = 11
NUM_COLS = 5
COL_NUM = 1
COL_NAME = 2
COL_TJ = 3
COL_EXAM = 4
COL_MOY = 5
LOCKED_COLS = (COL_NUM, COL_NAME, COL_MOY)
EDITABLE_COLS = (COL_TJ, COL_EXAM)

COLUMN_HEADERS = ['N°', 'NOM - POSTNOM - PRÉNOM', 'TJ/10', 'EXAM/10', 'MOY/20']

META_FILE_TOKEN = 'file_token'
META_STUDENT_COUNT = 'student_count'
META_FORMAT_VERSION = 'format_version'
FORMAT_VERSION = '2'

META_SESSION_ID = 'session_id'
META_CLASSE_ID = 'classe_id'
META_EC_ID = 'ec_id'
META_TJ_EVAL_ID = 'tj_evaluation_id'
META_EXAM_EVAL_ID = 'exam_evaluation_id'


def _slug(value, max_len=24) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^\w\-]+', '_', text.strip())
    return text.strip('_')[:max_len] or 'export'


def generate_notes_file_token() -> str:
    """Identifiant unique du fichier (présent dans le nom et les métadonnées)."""
    return secrets.token_hex(8).upper()



def build_fiche_cotation_download_name(
    ec,
    *,
    extension: str,
    file_token: str | None = None,
    avec_notes: bool | None = None,
) -> str:
    """Nom de fichier : code EC + nom EC + enseignant (+ jeton pour l'import Excel)."""
    parts = [_slug(ec.code, 30), _slug(ec.nom, 50)]
    enseignant = libelle_enseignant_ec(ec)
    if enseignant and enseignant != '—':
        parts.append(_slug(enseignant, 40))
    base = '_'.join(p for p in parts if p and p != 'export')
    if avec_notes is True:
        base = f'{base}_notes'
    elif avec_notes is False:
        base = f'{base}_vierge'
    ext = extension.lstrip('.')
    if file_token:
        return f'{base}_{file_token.upper()}_cotation.{ext}'
    return f'{base}.{ext}'


def build_export_filename(
    *,
    file_token: str,
    annee,
    session,
    classe,
    ec,
    avec_notes: bool | None = None,
) -> str:
    del annee, session, classe  # conservés pour compatibilité d'appel
    return build_fiche_cotation_download_name(
        ec, extension='xlsx', file_token=file_token, avec_notes=avec_notes,
    )


def extract_file_token_from_name(filename: str) -> str | None:
    if not filename:
        return None
    match = re.search(r'_([0-9A-F]{16})_', filename, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _normalize_header(value) -> str:
    if value is None:
        return ''
    text = unicodedata.normalize('NFKD', str(value).strip().lower())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('°', '').replace("'", ' ').replace('/', '_')
    text = re.sub(r'[^a-z0-9]+', '_', text).strip('_')
    aliases = {
        'n': 'numero_ordre',
        'no': 'numero_ordre',
        'nom_postnom_prenom': 'identite',
        'nom_nom_postnom_prenom': 'identite',
        'tj_10': 'tj',
        'tj10': 'tj',
        'exam_10': 'exam',
        'exam10': 'exam',
        'ratt_10': 'exam',
        'ratt10': 'exam',
        'moy_20': 'moy',
        'moy20': 'moy',
    }
    return aliases.get(text, text)


NUMERIC_CELL_FORMAT = '0.##'
_NON_NUMERIC_TEXT = re.compile(r'^-?\d+([.,]\d+)?$')


def _parse_note_sur_10(value, *, colonne='Note'):
    """Accepte uniquement des nombres (ou cellule vide) sur /10."""
    valeur, _effacer = _parse_note_import_cell(value, colonne=colonne)
    return valeur


def _parse_note_import_cell(value, *, colonne='Note'):
    """
    Interprète une cellule d'import.
    Retourne (valeur, effacer) : effacer=True supprime une note existante.
    """
    if value is None:
        return None, False
    if isinstance(value, bool):
        raise ValueError(f"{colonne} : saisissez uniquement un nombre entre 0 et 10.")

    if isinstance(value, (int, float, Decimal)):
        brut = value
    else:
        texte = str(value).strip()
        if texte == '':
            return None, True
        if texte in {'—', '-', '–', '/', 'N/A', 'n/a'}:
            return None, True
        if not _NON_NUMERIC_TEXT.match(texte):
            raise ValueError(
                f"{colonne} : valeur non numérique {texte!r}."
            )
        try:
            brut = Decimal(texte.replace(',', '.'))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{colonne} : note invalide {texte!r}.") from exc

    note = Decimal(str(brut))
    if note < 0 or note > BAREME_TJ_EXAM:
        raise ValueError(f"{colonne} : note hors barème (0–10) : {note}")
    return note, False


def _appliquer_format_numerique(cell):
    cell.number_format = NUMERIC_CELL_FORMAT


def _thin_border() -> Border:
    side = Side(style='thin', color='CBD5E1')
    return Border(left=side, right=side, top=side, bottom=side)


def _evaluations_session(ec, session):
    return list(
        Evaluation.objects.filter(ec=ec, session=session, active=True)
        .select_related('type_evaluation')
        .order_by('type_evaluation__ordre', 'pk')
    )


def resoudre_evaluations_cotation(ec, session):
    """
    Retourne (evaluation_tj, evaluation_exam_ou_ratt, tj_session).
    En rattrapage, TJ provient de la session principale ; EXAM = évaluation RATT sur S2.
    """
    evals = _evaluations_session(ec, session)
    if session.numero == 2:
        exam_eval = next((e for e in evals if est_type_rattrapage(e.type_evaluation)), None)
        s1 = session_principale(session)
        tj_evals = _evaluations_session(ec, s1) if s1 else []
        tj_eval = next((e for e in tj_evals if est_type_tj(e.type_evaluation)), None)
        return tj_eval, exam_eval, s1
    tj_eval = next((e for e in evals if est_type_tj(e.type_evaluation)), None)
    exam_eval = next((e for e in evals if est_type_exam(e.type_evaluation)), None)
    return tj_eval, exam_eval, session


def _cote_export(etudiant, evaluation):
    if not evaluation:
        return None
    statut, valeur = _lecture_cote_sur_10(etudiant, evaluation)
    if statut == 'saisie' and valeur is not None:
        return float(valeur)
    return None


def _moy_export(tj_val, exam_val):
    if tj_val is None or exam_val is None:
        return None
    moy = _moyenne_sur_20_depuis_bloc_tj_exam(Decimal(str(tj_val)), Decimal(str(exam_val)))
    return float(moy) if moy is not None else None


def build_lignes_cotation(ec, session, etudiants, *, avec_notes=True):
    """Prépare les lignes export (valeurs TJ/EXAM existantes si avec_notes)."""
    tj_eval, exam_eval, _ = resoudre_evaluations_cotation(ec, session)
    lignes = []
    for index, etudiant in enumerate(etudiants, start=1):
        tj_val = _cote_export(etudiant, tj_eval) if avec_notes else None
        exam_val = _cote_export(etudiant, exam_eval) if avec_notes else None
        lignes.append({
            'index': index,
            'etudiant': etudiant,
            'identite': etudiant.identite_cotation,
            'tj': tj_val,
            'exam': exam_val,
            'moy': _moy_export(tj_val, exam_val),
            'tj_editable': session.numero != 2,
        })
    return lignes, tj_eval, exam_eval


def build_notes_import_template(
    *,
    annee,
    session,
    classe,
    ec,
    etudiants,
    avec_notes=True,
):
    """Génère une fiche Excel alignée sur le PDF (TJ/10, EXAM/10, MOY/20)."""
    file_token = generate_notes_file_token()
    lignes, tj_eval, exam_eval = build_lignes_cotation(
        ec, session, etudiants, avec_notes=avec_notes,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = 'Cotation'
    ws.sheet_view.showGridLines = False

    title_font = Font(bold=True, size=14, color='0C4A6E')
    info_font = Font(size=10, color='334155')
    info_muted = Font(size=9, color='64748B', italic=True)
    header_font = Font(bold=True, color='FFFFFF', size=10)
    header_fill = PatternFill('solid', fgColor='003E82')
    locked_fill = PatternFill('solid', fgColor='F8FAFC')
    locked_font = Font(size=10, color='1E293B')
    editable_fill = PatternFill('solid', fgColor='FFFFFF')
    alt_locked_fill = PatternFill('solid', fgColor='F1F5F9')
    moy_fill = PatternFill('solid', fgColor='E0F2FE')

    last_col = get_column_letter(NUM_COLS)
    session_label = session.code
    if session.nom and session.nom.lower() not in session.code.lower():
        session_label = f'{session.code} ({session.nom})'

    ws.merge_cells(f'A1:{last_col}1')
    ws['A1'] = institution_nom_majuscules()
    ws['A1'].font = Font(bold=True, size=11, color='003E82')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 22

    ws.merge_cells(f'A2:{last_col}2')
    ws['A2'] = 'FICHE DE COTATION'
    ws['A2'].font = title_font
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 28

    exam_label = 'EXAM/10' if session.numero != 2 else 'EXAM/10 (rattrapage)'
    info_lines = [
        f"Identifiant fichier : {file_token}",
        f"Année académique : {annee.code if annee else '—'}",
        f"Session : {session_label} · Classe : {classe.promotion.nom} — {classe.code}",
        f"Cours : {ec.code} — {ec.nom}",
        f"Enseignant : {libelle_enseignant_ec(ec)}",
        f"Colonnes modifiables : TJ/10 · {exam_label} — nombres uniquement (0 à 10)",
        "MOY/20 calculée automatiquement — ne pas saisir de texte dans TJ/10 ni EXAM/10.",
        "Ne modifiez pas les noms ni n'ajoutez de lignes. Conservez le nom du fichier pour l'import.",
    ]
    for row_idx, line in enumerate(info_lines, start=INFO_START_ROW):
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=NUM_COLS)
        cell = ws.cell(row=row_idx, column=1, value=line)
        cell.font = info_muted if row_idx == INFO_START_ROW else info_font
        cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        ws.row_dimensions[row_idx].height = 18

    header_row = INFO_START_ROW + len(info_lines)
    data_start_row = header_row + 1

    border = _thin_border()
    for col_idx, header in enumerate(COLUMN_HEADERS, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[header_row].height = 22

    last_data_row = data_start_row + len(lignes) - 1
    for offset, ligne in enumerate(lignes):
        row_idx = data_start_row + offset
        etudiant = ligne['etudiant']
        row_values = (
            ligne['index'],
            ligne['identite'],
            ligne['tj'],
            ligne['exam'],
            None,
        )
        row_fill = alt_locked_fill if offset % 2 else locked_fill
        for col_idx, value in enumerate(row_values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = border
            cell.alignment = Alignment(
                horizontal='left' if col_idx == COL_NAME else 'center',
                vertical='center',
                wrap_text=col_idx == COL_NAME,
            )
            if col_idx == COL_MOY:
                tj_col = get_column_letter(COL_TJ)
                exam_col = get_column_letter(COL_EXAM)
                cell.value = (
                    f'=IF(AND(ISNUMBER({tj_col}{row_idx}),ISNUMBER({exam_col}{row_idx})),'
                    f'{tj_col}{row_idx}+{exam_col}{row_idx},"")'
                )
                cell.fill = moy_fill
                cell.font = locked_font
                cell.protection = Protection(locked=True)
            elif col_idx in EDITABLE_COLS:
                if value is not None:
                    cell.value = float(value)
                    _appliquer_format_numerique(cell)
                elif avec_notes:
                    cell.value = '—'
                else:
                    _appliquer_format_numerique(cell)
                if col_idx == COL_TJ and not ligne['tj_editable']:
                    cell.fill = row_fill
                    cell.protection = Protection(locked=True)
                else:
                    cell.fill = editable_fill
                    cell.protection = Protection(locked=False)
            else:
                cell.value = value
                cell.font = locked_font
                cell.fill = row_fill
                cell.protection = Protection(locked=True)

    if lignes:
        for col_letter, label in (
            (get_column_letter(COL_TJ), 'TJ/10'),
            (get_column_letter(COL_EXAM), 'EXAM/10'),
        ):
            dv = DataValidation(
                type='decimal',
                operator='between',
                formula1='0',
                formula2='10',
                allow_blank=True,
                showErrorMessage=True,
                errorTitle='Valeur non autorisée',
                error=f'{label} : saisissez uniquement un nombre entre 0 et 10.',
                showInputMessage=True,
                promptTitle=label,
                prompt='Nombre décimal entre 0 et 10 (aucun texte).',
            )
            dv.errorStyle = 'stop'
            ws.add_data_validation(dv)
            dv.add(f'{col_letter}{data_start_row}:{col_letter}{last_data_row}')

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 42
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 10
    ws.freeze_panes = f'A{data_start_row}'

    ws.protection.sheet = True
    ws.protection.enable()
    ws.protection.insertRows = False
    ws.protection.deleteRows = False
    ws.protection.insertColumns = False
    ws.protection.deleteColumns = False

    students_sheet = wb.create_sheet('_students')
    students_sheet.append(['row', 'numero_etudiant', 'identite'])
    for ligne in lignes:
        etu = ligne['etudiant']
        students_sheet.append([
            data_start_row + ligne['index'] - 1,
            etu.numero_etudiant,
            etu.identite_cotation,
        ])
    students_sheet.sheet_state = 'hidden'

    meta = wb.create_sheet('_meta')
    meta_entries = [
        (META_FORMAT_VERSION, FORMAT_VERSION),
        (META_FILE_TOKEN, file_token),
        (META_SESSION_ID, session.pk),
        (META_CLASSE_ID, classe.pk),
        (META_EC_ID, ec.pk),
        (META_TJ_EVAL_ID, tj_eval.pk if tj_eval else ''),
        (META_EXAM_EVAL_ID, exam_eval.pk if exam_eval else ''),
        (META_STUDENT_COUNT, len(lignes)),
        ('data_start_row', data_start_row),
        ('annee_code', annee.code if annee else ''),
        ('session_numero', session.numero),
    ]
    for idx, (key, value) in enumerate(meta_entries, start=1):
        meta[f'A{idx}'] = key
        meta[f'B{idx}'] = value
    meta.sheet_state = 'hidden'

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = build_export_filename(
        file_token=file_token,
        annee=annee,
        session=session,
        classe=classe,
        ec=ec,
        avec_notes=avec_notes,
    )
    return buffer, file_token, filename


def _find_header_row(sheet):
    for row_idx in range(1, min(sheet.max_row, 40) + 1):
        headers = [_normalize_header(cell.value) for cell in sheet[row_idx]]
        if 'identite' in headers or 'nom' in headers:
            if 'tj' in headers and 'exam' in headers:
                return row_idx, {header: idx for idx, header in enumerate(headers) if header}
    return None, {}


def _read_meta(workbook):
    if '_meta' not in workbook.sheetnames:
        return {}
    sheet = workbook['_meta']
    meta = {}
    for row in sheet.iter_rows(min_row=1, max_col=2, values_only=True):
        if row and row[0]:
            meta[str(row[0])] = row[1]
    return meta


def _read_students_map(workbook):
    if '_students' not in workbook.sheetnames:
        return {}
    sheet = workbook['_students']
    mapping = {}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        row_idx = int(row[0])
        mapping[row_idx] = {
            'numero_etudiant': str(row[1] or '').strip(),
            'identite': str(row[2] or '').strip(),
        }
    return mapping


def _validate_meta(meta, *, session, classe, ec, filename: str | None):
    if not meta or META_FILE_TOKEN not in meta:
        raise ValueError(
            "Fichier non reconnu. Utilisez le modèle Excel généré par e-Université "
            "(identifiant manquant)."
        )
    if str(meta.get(META_FORMAT_VERSION) or '') != FORMAT_VERSION:
        raise ValueError(
            "Format Excel obsolète. Téléchargez un nouveau modèle "
            "(fiche TJ/10 · EXAM/10 · MOY/20)."
        )

    file_token = str(meta[META_FILE_TOKEN]).strip().upper()
    name_token = extract_file_token_from_name(filename or '')
    if not name_token:
        raise ValueError(
            "Nom de fichier invalide. Conservez le nom généré à l'export "
            "(code EC, nom EC, enseignant et identifiant interne)."
        )
    if name_token != file_token:
        raise ValueError(
            "Le nom du fichier ne correspond pas à son identifiant interne. "
            "Ne renommez pas le fichier exporté."
        )

    if int(meta.get(META_SESSION_ID) or 0) != session.pk:
        raise ValueError("Ce fichier concerne une autre session.")
    if int(meta.get(META_EC_ID) or 0) != ec.pk:
        raise ValueError("Ce fichier concerne un autre cours (EC).")
    if meta.get(META_CLASSE_ID) and int(meta[META_CLASSE_ID]) != classe.pk:
        raise ValueError("Ce fichier concerne une autre classe.")

    return file_token


def parse_notes_import_workbook(
    uploaded_file,
    *,
    session,
    classe,
    ec,
    etudiants_par_numero: dict[str, object],
    filename: str | None = None,
):
    """
    Lit une fiche Excel remplie et retourne les notes TJ/EXAM à enregistrer.
    etudiants_par_numero : {numero_etudiant: etudiant}
    """
    workbook = load_workbook(uploaded_file, data_only=True)
    meta = _read_meta(workbook)
    _validate_meta(meta, session=session, classe=classe, ec=ec, filename=filename)

    tj_eval_id = int(meta.get(META_TJ_EVAL_ID) or 0) or None
    exam_eval_id = int(meta.get(META_EXAM_EVAL_ID) or 0) or None
    tj_eval = Evaluation.objects.filter(pk=tj_eval_id).first() if tj_eval_id else None
    exam_eval = Evaluation.objects.filter(pk=exam_eval_id).first() if exam_eval_id else None

    if not tj_eval and not exam_eval:
        tj_eval, exam_eval, _ = resoudre_evaluations_cotation(ec, session)

    expected_count = int(meta.get(META_STUDENT_COUNT) or len(etudiants_par_numero))
    data_start_row = int(meta.get('data_start_row') or DEFAULT_DATA_START_ROW)
    students_map = _read_students_map(workbook)

    sheet = workbook['Cotation'] if 'Cotation' in workbook.sheetnames else workbook.active
    header_row, index_map = _find_header_row(sheet)
    if not header_row:
        raise ValueError(
            "En-têtes introuvables (NOM - POSTNOM - PRÉNOM, TJ/10, EXAM/10, MOY/20)."
        )

    if 'tj' not in index_map or 'exam' not in index_map:
        raise ValueError("Colonnes TJ/10 et EXAM/10 requises.")

    lignes = []
    errors = []
    seen_numeros: dict[str, int] = {}
    imported_rows = 0

    for line_number, row in enumerate(
        sheet.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        if not any(row):
            continue

        def cell(name):
            idx = index_map.get(name)
            return row[idx] if idx is not None and idx < len(row) else None

        identite_fichier = str(cell('identite') or '').strip()
        if not identite_fichier and not any(cell(k) for k in ('tj', 'exam')):
            continue

        student_meta = students_map.get(line_number, {})
        numero = student_meta.get('numero_etudiant', '')
        identite_ref = student_meta.get('identite', '')

        if not numero:
            errors.append(f"Ligne {line_number} : étudiant non identifié (fichier altéré).")
            continue

        if numero in seen_numeros:
            errors.append(f"Ligne {line_number} : N° étudiant en double ({numero}).")
            continue
        seen_numeros[numero] = line_number
        imported_rows += 1

        etudiant = etudiants_par_numero.get(numero)
        if etudiant is None:
            errors.append(
                f"Ligne {line_number} : étudiant {numero} non autorisé "
                "(ajout ou classe incorrecte)."
            )
            continue

        if identite_ref and identite_fichier and identite_fichier != identite_ref:
            errors.append(
                f"Ligne {line_number} : l'identité a été modifiée pour {numero}."
            )
            continue

        tj_value = None
        exam_value = None
        tj_effacer = False
        exam_effacer = False
        try:
            tj_value, tj_effacer = _parse_note_import_cell(cell('tj'), colonne='TJ/10')
            exam_value, exam_effacer = _parse_note_import_cell(cell('exam'), colonne='EXAM/10')
        except ValueError as exc:
            errors.append(f"Ligne {line_number} : {exc}")
            continue

        if (
            tj_value is None and exam_value is None
            and not tj_effacer and not exam_effacer
        ):
            continue

        if session.numero == 2 and tj_value is not None:
            errors.append(
                f"Ligne {line_number} : la colonne TJ/10 est en lecture seule "
                "en session de rattrapage."
            )
            tj_value = None

        if session.numero == 2 and tj_effacer:
            errors.append(
                f"Ligne {line_number} : la colonne TJ/10 est en lecture seule "
                "en session de rattrapage."
            )
            tj_effacer = False

        lignes.append({
            'etudiant': etudiant,
            'tj_value': tj_value,
            'exam_value': exam_value,
            'tj_effacer': tj_effacer,
            'exam_effacer': exam_effacer,
            'tj_evaluation': tj_eval,
            'exam_evaluation': exam_eval,
            'line_number': line_number,
        })

    expected_numeros = set(etudiants_par_numero.keys())
    found_numeros = set(seen_numeros.keys())
    extra = found_numeros - expected_numeros
    if extra:
        errors.append(
            "Étudiants non autorisés dans le fichier : " + ', '.join(sorted(extra)[:5])
        )

    if imported_rows > expected_count:
        errors.append(
            f"Le fichier contient {imported_rows} lignes étudiant "
            f"au lieu de {expected_count}."
        )

    if errors and not lignes:
        raise ValueError(errors[0])

    return lignes, errors
