"""
Génération PDF — Fiche de scolarité d'un étudiant.
"""
from __future__ import annotations

import os
from datetime import date
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor('#0b3984')
INK_MUTED = colors.HexColor('#4a5568')
LINE = colors.HexColor('#cbd5e1')
HEADER_BG = colors.HexColor('#e8eef7')


def _asset_path(*parts):
    return os.path.join(str(settings.BASE_DIR), *parts)


def _find_logo_path():
    for parts in (
        ('static', 'images', 'logoeifi.png'),
        ('static', 'image', 'logoeifi.png'),
        ('media', 'logoeifi.png'),
    ):
        path = _asset_path(*parts)
        if os.path.exists(path):
            return path
    return None


def _logo_flowable(width_mm=18):
    path = _find_logo_path()
    if not path:
        return None
    img = RLImage(path)
    img.drawHeight = width_mm * mm * img.drawHeight / img.drawWidth
    img.drawWidth = width_mm * mm
    return img


def _photo_flowable(student, width_mm=28):
    photo = getattr(student, 'photo', None)
    if not photo or not getattr(photo, 'name', None):
        return None
    try:
        path = photo.path
    except Exception:
        return None
    if not path or not os.path.exists(path):
        return None
    img = RLImage(path)
    img.drawWidth = width_mm * mm
    img.drawHeight = width_mm * mm * 1.25
    return img


def _safe(value, default='—'):
    text = (str(value).strip() if value is not None else '')
    return text or default


def _styles():
    base = ParagraphStyle(
        'fs_base',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=INK_MUTED,
        alignment=TA_LEFT,
    )
    return {
        'meta': ParagraphStyle(
            'fs_meta',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=INK,
        ),
        'meta_right': ParagraphStyle(
            'fs_meta_right',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'title': ParagraphStyle(
            'fs_title',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=INK,
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=4,
        ),
        'section': ParagraphStyle(
            'fs_section',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
        ),
        'label': ParagraphStyle(
            'fs_label',
            parent=base,
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=INK_MUTED,
        ),
        'value': ParagraphStyle(
            'fs_value',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1a202c'),
        ),
        'cell': ParagraphStyle(
            'fs_cell',
            parent=base,
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#1a202c'),
        ),
        'cell_head': ParagraphStyle(
            'fs_cell_head',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'footer': ParagraphStyle(
            'fs_footer',
            parent=base,
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=10,
            textColor=INK_MUTED,
            alignment=TA_RIGHT,
        ),
        'sig': ParagraphStyle(
            'fs_sig',
            parent=base,
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#1a202c'),
            alignment=TA_CENTER,
        ),
    }


def _identity_row(label, value, styles):
    return [
        Paragraph(label, styles['label']),
        Paragraph(_safe(value), styles['value']),
    ]


def build_fiche_scolarite_pdf(student, inscriptions) -> bytes:
    """Construit le PDF de la fiche de scolarité et retourne les bytes."""
    buffer = BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.4 * cm,
    )
    content_width = A4[0] - 3.2 * cm
    story = []

    logo = _logo_flowable()
    logo_cell = logo or Paragraph('E.I.FI', styles['meta'])
    header = Table(
        [[
            logo_cell,
            Paragraph(
                '<b>ECOLE INFORMATIQUE DES FINANCES</b><br/>'
                'E.I.FI<br/>'
                '<font size="8">Fiche administrative de scolarité</font>',
                styles['meta'],
            ),
            Paragraph(
                f'Année acad.<br/><b>{_current_annee_label(inscriptions)}</b>',
                styles['meta_right'],
            ),
        ]],
        colWidths=[2.2 * cm, content_width - 5.4 * cm, 3.2 * cm],
    )
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, INK),
    ]))
    story.append(header)
    story.append(Spacer(1, 10))
    story.append(Paragraph('FICHE DE SCOLARITÉ', styles['title']))
    story.append(Spacer(1, 6))

    photo = _photo_flowable(student)
    id_rows = [
        _identity_row('Matricule', student.numero_etudiant, styles),
        _identity_row('Nom complet', student.nom_complet, styles),
        _identity_row('Sexe', student.get_sexe_display(), styles),
        _identity_row(
            'Né(e) le',
            student.date_naissance.strftime('%d/%m/%Y') if student.date_naissance else '—',
            styles,
        ),
        _identity_row('Lieu de naissance', student.lieu_naissance, styles),
        _identity_row('Nationalité', student.nationalite, styles),
        _identity_row('Téléphone', student.telephone, styles),
        _identity_row('Email', student.email, styles),
        _identity_row('Adresse', student.adresse, styles),
        _identity_row('Statut', student.get_statut_display(), styles),
    ]
    id_table = Table(id_rows, colWidths=[3.4 * cm, content_width - 3.4 * cm - (3.4 * cm if photo else 0)])
    id_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, LINE),
    ]))

    story.append(Paragraph('1. Identité de l’étudiant', styles['section']))
    if photo:
        block = Table(
            [[id_table, photo]],
            colWidths=[content_width - 3.4 * cm, 3.4 * cm],
        )
        block.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(block)
    else:
        story.append(id_table)

    story.append(Paragraph('2. Parcours de scolarité', styles['section']))
    head = [
        Paragraph('Année', styles['cell_head']),
        Paragraph('Filière / Promotion', styles['cell_head']),
        Paragraph('Classe', styles['cell_head']),
        Paragraph('N° inscription', styles['cell_head']),
        Paragraph('Statut', styles['cell_head']),
        Paragraph('Date', styles['cell_head']),
    ]
    rows = [head]
    for ins in inscriptions:
        classe = ins.classe
        promo = getattr(classe, 'promotion', None) if classe else None
        filiere = getattr(promo, 'filiere', None) if promo else None
        filiere_label = '—'
        if filiere or promo:
            parts = []
            if filiere:
                parts.append(filiere.code or filiere.nom)
            if promo:
                parts.append(promo.code or promo.nom)
            filiere_label = ' / '.join(str(p) for p in parts if p)
        rows.append([
            Paragraph(_safe(ins.annee_academique.code if ins.annee_academique_id else None), styles['cell']),
            Paragraph(_safe(filiere_label), styles['cell']),
            Paragraph(_safe(classe), styles['cell']),
            Paragraph(_safe(ins.numero_inscription), styles['cell']),
            Paragraph(_safe(ins.get_statut_display()), styles['cell']),
            Paragraph(
                ins.date_inscription.strftime('%d/%m/%Y') if ins.date_inscription else '—',
                styles['cell'],
            ),
        ])

    empty = not inscriptions
    if empty:
        rows.append([
            Paragraph('Aucune inscription enregistrée.', styles['cell']),
            '', '', '', '', '',
        ])

    col_widths = [
        2.2 * cm,
        4.2 * cm,
        3.0 * cm,
        3.0 * cm,
        2.6 * cm,
        content_width - 15.0 * cm,
    ]
    parcours = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    if empty:
        style_cmds.append(('SPAN', (0, 1), (-1, 1)))
    parcours.setStyle(TableStyle(style_cmds))
    story.append(parcours)

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        f'Fait à Kinshasa, le {date.today().strftime("%d/%m/%Y")}',
        styles['footer'],
    ))
    story.append(Spacer(1, 28))
    story.append(Paragraph('Le Secrétaire Général Académique', styles['sig']))

    doc.build(story)
    return buffer.getvalue()


def _current_annee_label(inscriptions) -> str:
    if not inscriptions:
        return '—'
    first = inscriptions[0]
    return first.annee_academique.code if first.annee_academique_id else '—'


def build_fiche_scolarite_filename(student) -> str:
    matricule = (student.numero_etudiant or 'etudiant').replace('/', '-')
    return f'fiche_scolarite_{matricule}.pdf'
