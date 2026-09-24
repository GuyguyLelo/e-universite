"""
Génère le document Word « Délibération LMD et compensation » (e-Université).
Usage : python deliberations/generate_doc_deliberation.py
"""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'docs'
OUTPUT_FILE = OUTPUT_DIR / 'Deliberation_LMD_et_compensation_e-Université.docx'
OUTPUT_FILE_FALLBACK = OUTPUT_DIR / 'Deliberation_LMD_et_compensation_e-Université_v1.2.docx'

COLOR_PRIMARY = RGBColor(0x03, 0x69, 0xA1)
COLOR_ACCENT = RGBColor(0x0E, 0xA5, 0xE9)
COLOR_TEXT = RGBColor(0x1E, 0x29, 0x3B)
COLOR_MUTED = RGBColor(0x64, 0x74, 0x8B)


def set_cell_shading(cell, fill_hex: str):
    shading = cell._tc.get_or_add_tcPr()
    shd = shading.makeelement(qn('w:shd'), {
        qn('w:fill'): fill_hex,
        qn('w:val'): 'clear',
    })
    shading.append(shd)


def configure_styles(doc: Document):
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)
    normal.font.color.rgb = COLOR_TEXT
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for level, size in ((1, 16), (2, 13), (3, 11)):
        style = doc.styles[f'Heading {level}']
        style.font.name = 'Calibri'
        style.font.bold = True
        style.font.color.rgb = COLOR_PRIMARY if level == 1 else COLOR_ACCENT
        style.font.size = Pt(size)
        style.paragraph_format.space_before = Pt(14 if level == 1 else 10)
        style.paragraph_format.space_after = Pt(6)


def add_cover(doc: Document):
    for _ in range(3):
        doc.add_paragraph()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('e-Université')
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = COLOR_ACCENT

    main = doc.add_paragraph()
    main.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = main.add_run('Délibération LMD\net mécanismes de compensation')
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = COLOR_PRIMARY

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run('Guide fonctionnel — module Délibérations')
    run.font.size = Pt(12)
    run.font.color.rgb = COLOR_MUTED

    doc.add_paragraph()
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run(f'Version 1.2 — {date.today().strftime("%d/%m/%Y")}')
    run.font.size = Pt(10)
    run.font.color.rgb = COLOR_MUTED

    doc.add_page_break()


def add_bullet_list(doc: Document, items: list[str]):
    for item in items:
        p = doc.add_paragraph(item, style='List Bullet')
        p.paragraph_format.left_indent = Cm(0.75)


def add_table(doc: Document, headers: list[str], rows: list[list[str]]):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for col, header in enumerate(headers):
        cell = table.rows[0].cells[col]
        cell.text = header
        set_cell_shading(cell, 'E0F2FE')
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.color.rgb = COLOR_PRIMARY
                run.font.size = Pt(10)

    for row_idx, row_data in enumerate(rows, start=1):
        for col_idx, value in enumerate(row_data):
            cell = table.rows[row_idx].cells[col_idx]
            cell.text = value
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)

    doc.add_paragraph()


def build_document() -> Document:
    doc = Document()
    configure_styles(doc)

    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    add_cover(doc)

    doc.add_heading('1. Objet du document', level=1)
    doc.add_paragraph(
        'Ce document décrit le fonctionnement du moteur de délibération intégré à la plateforme '
        'e-Université : calcul des notes, règles de validation, mécanismes de compensation, '
        'capitalisation des crédits ECTS et décisions du jury (semestrielle, annuelle et cycle Master).'
    )

    doc.add_heading('2. Chaîne de calcul des notes', level=1)
    doc.add_heading('2.1 Note de l’élément constitutif (EC)', level=2)
    add_bullet_list(doc, [
        'Travaux journaliers (TJ) saisis sur /10.',
        'Examen du semestre saisi sur /10.',
        'Session principale : note EC sur /20 = moyenne arithmétique (TJ + examen) / 2, ramenée sur 20.',
        'Rattrapage : si l’examen est strictement inférieur à 10/10, la note de rattrapage (session 2) remplace l’examen.',
        'Délibération sur session finale (souvent S2) : fusion TJ (session 1) + meilleure note entre examen S1 et rattrapage S2.',
    ])

    doc.add_heading('2.2 Note de l’unité d’enseignement (UE)', level=2)
    doc.add_paragraph(
        'Moyenne pondérée des notes EC de l’UE, selon le coefficient de chaque EC.'
    )

    doc.add_heading('2.3 Moyenne du semestre', level=2)
    doc.add_paragraph(
        'Moyenne pondérée des notes UE du semestre, selon le coefficient de chaque UE '
        '(crédits ECTS ou coefficients selon la maquette).'
    )

    doc.add_heading('2.4 Workflow des sessions', level=2)
    add_bullet_list(doc, [
        'Session principale (S1) : saisie TJ + examen, puis verrouillage.',
        'Session de rattrapage (S2) : ouverte pour les étudiants convoqués (examen < 10/10), puis verrouillage.',
        'La délibération semestrielle s’appuie sur la session finalisée (priorité S2 si délibération terminée).',
        'Après délibération : session marquée « délibération faite » et verrouillée ; grille de notes PDF enregistrée.',
    ])

    doc.add_heading('3. Seuil de validation et note éliminatoire', level=1)
    doc.add_paragraph(
        'Le seuil par défaut est fixé à 10,00/20 (configurable par promotion dans les Paramètres LMD). '
        'Une note est validée si elle est supérieure ou égale au seuil : '
        '10,00/20 est validé (règle ≥ 10).'
    )
    add_bullet_list(doc, [
        'Seuil global : Paramètres LMD → seuil_validation.',
        'Seuil spécifique possible sur chaque UE ou EC (sinon repli sur le seuil global).',
        'La validation, la capitalisation et les décisions du jury appliquent tous cette règle inclusive (≥).',
    ])

    doc.add_heading('3.1 Note éliminatoire par EC', level=2)
    add_bullet_list(doc, [
        'Champ optionnel sur chaque EC (maquette → Élément constitutif → Note éliminatoire /20).',
        'Si renseignée (ex. 7,00/20), une note EC strictement inférieure est dite « éliminatoire ».',
        'Une note éliminatoire bloque la validation de l’EC et la compensation intra-UE pour cet EC.',
        'Pour obtenir la décision « Admis » (sans compensation), il ne doit exister aucune note éliminatoire.',
        'Présence d’une note éliminatoire avec moyenne ≥ 10 et toutes les UE validées → « Admis par compensation ».',
    ])

    doc.add_heading('4. Mécanismes de compensation', level=1)
    doc.add_paragraph(
        'La compensation permet de valider un élément dont la note individuelle est insuffisante '
        '(strictement inférieure au seuil) grâce à une moyenne favorable à un niveau supérieur '
        'qui atteint ou dépasse le seuil (≥). '
        'Chaque niveau peut être activé ou désactivé dans les Paramètres LMD.'
    )

    doc.add_heading('4.1 Compensation intra-UE', level=2)
    add_bullet_list(doc, [
        'Un EC en échec (note < seuil) peut être validé si la moyenne de son UE atteint ou dépasse le seuil (≥).',
        'Conditions : EC.compensation_autorisee = Oui ET compensation_intra_ue activée.',
        'Exception : si la note EC est éliminatoire (note < note_eliminatoire de l’EC), l’EC reste non validé.',
        'Effet : tous les EC de l’UE sont considérés validés pour la délibération et la capitalisation.',
    ])

    doc.add_heading('4.2 Compensation intra-semestre', level=2)
    add_bullet_list(doc, [
        'Une UE en échec peut être validée si la moyenne du semestre atteint ou dépasse le seuil (≥).',
        'Conditions : UE.compensation_autorisee = Oui ET compensation_intra_semestre activée.',
        'Effet : l’UE est validée pour la délibération ; les EC peuvent capitaliser selon les règles EC.',
    ])

    doc.add_heading('4.3 Compensation annuelle', level=2)
    add_bullet_list(doc, [
        'Lors de la délibération annuelle (S1 + S2), si la moyenne annuelle atteint ou dépasse le seuil (≥), '
        'les UE non validées individuellement mais éligibles (compensation_autorisee) peuvent compter leurs crédits.',
        'La moyenne annuelle est pondérée par les crédits totaux de chaque semestre.',
        'Condition : compensation_annuelle activée dans les Paramètres LMD.',
        'Prérequis : les deux délibérations semestrielles (S1 et S2) doivent être terminées.',
    ])

    doc.add_heading('5. Capitalisation des crédits', level=1)
    add_table(doc,
        headers=['Situation', 'Crédits comptabilisés'],
        rows=[
            ['UE validée (directement ou par compensation)', 'Crédits ECTS complets de l’UE'],
            ['UE non validée', 'EC validés individuellement (note ≥ seuil), si capitalisation EC activée'],
            ['EC non capitalisable', 'Exclus du total même si validé'],
            ['Plafond', 'Total plafonné aux crédits du semestre (maquette LMD, souvent 30 ECTS)'],
        ],
    )

    doc.add_heading('6. Décisions du jury', level=1)
    doc.add_heading('6.1 Délibération semestrielle', level=2)
    add_table(doc,
        headers=['Décision', 'Conditions'],
        rows=[
            ['Admis', 'Moyenne générale ≥ 10/20, toutes les UE validées directement (≥ seuil) et aucune note éliminatoire EC.'],
            ['Admis par compensation', 'Moyenne générale ≥ 10/20, toutes les UE validées mais UE compensée et/ou note éliminatoire EC présente.'],
            ['Défaillant', 'Absence non justifiée ou note manquante sur une évaluation obligatoire (TJ, examen, rattrapage).'],
            ['Ajourné', 'Moyenne générale < 10/20, ou moyenne ≥ 10 avec UE non validées et passage avec dettes impossible.'],
            ['Admis avec dettes', 'Moyenne ≥ 10/20, passage au niveau supérieur avec certaines UE non validées à rattraper (si option activée).'],
        ],
    )
    doc.add_paragraph(
        'Ordre de priorité du moteur : Défaillant → Ajourné (moyenne non calculable ou < 10) → '
        'Admis avec dettes → Admis par compensation → Admis.'
    )

    doc.add_heading('6.2 Mentions (semestre ou annuel)', level=2)
    add_table(doc,
        headers=['Moyenne', 'Mention'],
        rows=[
            ['≥ 16,00', 'Très bien'],
            ['≥ 14,00', 'Bien'],
            ['≥ 12,00', 'Assez bien'],
            ['≥ 10,00', 'Passable'],
            ['< 10,00', 'Aucune mention'],
        ],
    )

    doc.add_heading('6.3 Délibération annuelle (passage de promotion)', level=2)
    add_bullet_list(doc, [
        'Type « annuelle » : agrégation des semestres S1 et S2 sur l’année académique.',
        'Même barème décisionnel que la délibération semestrielle (Admis, Admis par compensation, Défaillant, Ajourné, Admis avec dettes).',
        'Seuil crédits minimum annuel = seuil_credits_minimum × 2 (défaut 60 ECTS).',
        'Décision « Admis avec dettes » : passage en promotion supérieure avec EC non capitalisés.',
    ])
    doc.add_heading('6.4 Délibération cycle Master (M1 + M2)', level=2)
    add_bullet_list(doc, [
        'Type « cycle_master » : agrégation des années Master 1 et Master 2 (4 semestres LMD).',
        'Promotion cible : Master 2 ; résultats M1 issus de la promotion précédente dans la filière.',
        'Prérequis : délibérations annuelles terminées pour M1 et M2 sur les années concernées.',
        'Moyenne du cycle pondérée par les crédits totaux M1 et M2 ; même logique décisionnelle (≥ seuil).',
        'Seuil crédits minimum cycle = seuil_credits_minimum × 4 (défaut 120 ECTS).',
    ])

    doc.add_heading('7. Gestion des dettes (module e-Université)', level=1)
    doc.add_paragraph(
        'Le module Gestion des dettes recense les étudiants passés en promotion supérieure '
        '(ex. 1re → 2e année) ayant des EC dont la note finale est strictement inférieure à 10/20 '
        'sur la promotion précédente (année N-1). Une note de 10,00/20 exactement n’est pas une dette.'
    )
    add_bullet_list(doc, [
        'Critère dette : note EC < 10/20 (indépendamment de la validation par compensation).',
        'Un EC validé par compensation mais dont la note brute reste < 10/20 apparaît en dette.',
        'Les dettes correspondent aux cours à reprendre ou à valider en promotion supérieure.',
    ])

    doc.add_heading('8. Gestion du jury et accès système', level=1)
    add_bullet_list(doc, [
        'Menu Délibérations → Gestion du Jury : comptes du groupe « Jury » et composition par délibération.',
        'Groupe Django « Jury » : consultation des délibérations assignées, modification des décisions.',
        'Président et membres sont désignés sur chaque fiche délibération.',
        'Un membre du jury ne voit que les délibérations où il est président ou membre.',
        'Commande d’initialisation : python manage.py seed_jury_group --assign <utilisateur>.',
    ])

    doc.add_heading('9. Paramètres configurables', level=1)
    doc.add_heading('9.1 Paramètres LMD (par promotion)', level=2)
    add_table(doc,
        headers=['Paramètre', 'Description', 'Valeur par défaut'],
        rows=[
            ['seuil_validation', 'Seuil de validation (/20)', '10,00'],
            ['compensation_intra_ue', 'Compensation EC par moyenne UE', 'Oui'],
            ['compensation_intra_semestre', 'Compensation UE par moyenne semestre', 'Oui'],
            ['compensation_annuelle', 'Compensation annuelle des crédits', 'Oui'],
            ['capitalisation_ue', 'Capitalisation au niveau UE', 'Oui'],
            ['capitalisation_ec', 'Capitalisation au niveau EC', 'Oui'],
            ['passage_avec_dettes', 'Autoriser le passage avec dettes', 'Oui'],
            ['seuil_credits_minimum', 'Crédits min. pour passage avec dettes (semestre)', '30'],
        ],
    )
    doc.add_heading('9.2 Paramètres EC (maquette)', level=2)
    add_table(doc,
        headers=['Champ', 'Description', 'Valeur par défaut'],
        rows=[
            ['seuil_validation', 'Seuil de validation de l’EC (/20)', '10,00'],
            ['note_eliminatoire', 'Seuil éliminatoire optionnel (/20)', 'Vide (désactivé)'],
            ['compensation_autorisee', 'Autoriser la compensation intra-UE', 'Oui'],
            ['capitalisable', 'EC comptabilisé en capitalisation partielle', 'Oui'],
        ],
    )

    doc.add_heading('10. Workflow recommandé', level=1)
    steps = [
        'Configurer les Paramètres LMD par promotion et les seuils EC (validation, note éliminatoire).',
        'Saisir les notes TJ et examen (session principale).',
        'Verrouiller la session principale.',
        'Préparer et saisir le rattrapage si nécessaire (examen < 10/10).',
        'Verrouiller la session de rattrapage.',
        'Composer le jury (Gestion du Jury) et créer la délibération semestrielle.',
        'Lancer le calcul LMD pour la promotion concernée.',
        'Générer le procès-verbal et la grille de notes PDF.',
        'En fin d’année : délibération annuelle S1+S2 pour le passage de promotion.',
        'En fin de Master 2 : délibération cycle Master M1+M2 pour la décision de diplôme.',
        'Consulter la Gestion des dettes pour le suivi des EC reportés.',
    ]
    for idx, step in enumerate(steps, start=1):
        p = doc.add_paragraph()
        run = p.add_run(f'{idx}. ')
        run.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        p.add_run(step)

    doc.add_paragraph()
    note = doc.add_paragraph()
    run = note.add_run(
        'Document généré automatiquement par e-Université — à usage institutionnel interne.'
    )
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = COLOR_MUTED
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER

    return doc


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = build_document()
    try:
        doc.save(OUTPUT_FILE)
        print(f'Document créé : {OUTPUT_FILE}')
    except PermissionError:
        doc.save(OUTPUT_FILE_FALLBACK)
        print(
            f'Fichier principal verrouillé (fermez Word). '
            f'Document créé : {OUTPUT_FILE_FALLBACK}'
        )


if __name__ == '__main__':
    main()
