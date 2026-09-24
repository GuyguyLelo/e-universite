"""Génération PDF — fiche de cotation vierge pour saisie manuelle par l'enseignant."""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from io import BytesIO
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr as qr_barcode
from reportlab.graphics.shapes import Drawing

FICHE_COL_COUNT = 4
CELLULE_NOTE_VIDE = ' '
NOTE_MANQUANTE = '—'


def _format_note_pdf(value, *, vide=CELLULE_NOTE_VIDE) -> str:
    if value is None:
        return vide
    text = format(Decimal(str(value)), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


def _asset_path(*parts):
    return os.path.join(str(settings.BASE_DIR), *parts)


from config.pdf_entete import institution_logo_path, institution_nom_majuscules, institution_sigle


def _logo_flowable(path, width_mm=20):
    if not path or not os.path.exists(path):
        return None
    img = RLImage(path)
    img.drawHeight = width_mm * mm * img.drawHeight / img.drawWidth
    img.drawWidth = width_mm * mm
    return img


def _get_public_base_url():
    configured = getattr(settings, 'CARD_PUBLIC_BASE_URL', None) or os.environ.get('CARD_PUBLIC_BASE_URL')
    if configured:
        return configured.rstrip('/') + '/'
    return 'http://127.0.0.1:8000/'


def _fiche_cotation_qr_payload(*, session, classe, ec):
    """URL de la fiche encodée dans le QR (mêmes paramètres que le lien de téléchargement)."""
    path = reverse('evaluations:fiche_cotation_pdf')
    query = f'session={session.pk}&classe={classe.pk}&ec={ec.pk}'
    return urljoin(_get_public_base_url(), path.lstrip('/') + '?' + query)


class _QrCodeFlowable(Flowable):
    """QR code vectoriel (ReportLab) — pas de dépendance qrcode/PIL."""

    def __init__(self, payload, size_mm=14):
        super().__init__()
        self.payload = payload or ''
        self.size = size_mm * mm

    def wrap(self, avail_width, avail_height):
        return self.size, self.size

    def draw(self):
        if not self.payload:
            return
        widget = qr_barcode.QrCodeWidget(self.payload)
        bounds = widget.getBounds()
        bw = bounds[2] - bounds[0]
        bh = bounds[3] - bounds[1]
        drawing = Drawing(
            self.size,
            self.size,
            transform=[self.size / bw, 0, 0, self.size / bh, 0, 0],
        )
        drawing.add(widget)
        renderPDF.draw(drawing, self.canv, 0, 0)


def _qr_flowable(payload, size_mm=14):
    if not payload:
        return None
    return _QrCodeFlowable(payload, size_mm=size_mm)


def _build_pdf_header(annee, section_label, meta_style, *, qr_payload=None):
    logo = _logo_flowable(institution_logo_path(), width_mm=14)
    ink_primary = colors.HexColor('#003E82')
    header_title = ParagraphStyle(
        'FicheCotationHeaderTitle',
        parent=meta_style,
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=8.5,
        alignment=TA_LEFT,
        textColor=ink_primary,
        spaceBefore=0,
        spaceAfter=0,
    )
    header_right = ParagraphStyle(
        'FicheCotationHeaderRight',
        parent=meta_style,
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=ink_primary,
    )
    year_text = annee.code if annee else '—'
    qr = _qr_flowable(qr_payload, size_mm=14)
    logo_cell = logo if logo else Paragraph(
        institution_sigle(),
        ParagraphStyle(
            'FicheCotationLogoFallback',
            parent=meta_style,
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=ink_primary,
            alignment=TA_CENTER,
        ),
    )

    header_table = Table(
        [[
            logo_cell,
            Paragraph(
                f'<b>{institution_nom_majuscules()}</b>'
                f'<br/><font size="7" color="#475569">{section_label}</font>',
                header_title,
            ),
            qr if qr else '',
            Paragraph(
                f'<font size="7" color="#475569">ANNÉE ACADÉMIQUE</font><br/>{year_text}',
                header_right,
            ),
        ]],
        colWidths=[18 * mm, 104 * mm, 18 * mm, 36 * mm],
    )
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#003E82')),
        ('LINEBELOW', (0, 0), (-1, -1), 0.8, colors.HexColor('#007FFF')),
        ('INNERGRID', (0, 0), (-1, -1), 0.2, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return header_table





def _notes_table_style(sig_start_row=None, has_header=True, col_count=FICHE_COL_COUNT, *, compact=False):

    last_col = col_count - 1
    row_pad = 4 if compact else 5
    note_col_pad = 6 if compact else 9

    style_cmds = [

        ('FONTSIZE', (0, 0), (-1, -1), 8),

        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),

        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        ('TOPPADDING', (0, 0), (-1, -1), row_pad),

        ('BOTTOMPADDING', (0, 0), (-1, -1), row_pad),

        ('LEFTPADDING', (0, 0), (-1, -1), 4),

        ('RIGHTPADDING', (0, 0), (-1, -1), 4),

    ]

    name_align_start = 1 if has_header else 0

    style_cmds.append(('ALIGN', (1, name_align_start), (1, -1), 'LEFT'))

    style_cmds.append(('VALIGN', (1, name_align_start), (1, -1), 'MIDDLE'))

    if has_header:

        style_cmds.extend([

            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284c7')),

            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),

            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

        ])

    grid_end = (sig_start_row - 1) if sig_start_row else -1

    style_cmds.append(('GRID', (0, 0), (-1, grid_end), 0.4, colors.HexColor('#94a3b8')))

    row_bg_start = 1 if has_header else 0
    data_end = (sig_start_row - 1) if sig_start_row else -1
    if data_end < row_bg_start and sig_start_row is None:
        data_end = -1
    if data_end >= row_bg_start or data_end == -1:
        end_row = data_end if data_end >= row_bg_start else -1
        style_cmds.extend([
            ('TOPPADDING', (2, row_bg_start), (3, end_row), note_col_pad),
            ('BOTTOMPADDING', (2, row_bg_start), (3, end_row), note_col_pad),
        ])
    if sig_start_row is None:

        style_cmds.append(

            ('ROWBACKGROUNDS', (0, row_bg_start), (-1, -1), [colors.white, colors.HexColor('#f0f9ff')])

        )

    else:

        style_cmds.append(

            ('ROWBACKGROUNDS', (0, row_bg_start), (-1, sig_start_row - 1), [colors.white, colors.HexColor('#f0f9ff')])

        )

        style_cmds.extend([

            ('SPAN', (0, sig_start_row), (last_col, sig_start_row)),

            ('SPAN', (0, sig_start_row + 1), (last_col, sig_start_row + 1)),

            ('LINEABOVE', (0, sig_start_row + 1), (last_col, sig_start_row + 1), 0.5, colors.HexColor('#64748b')),

            ('TOPPADDING', (0, sig_start_row), (-1, sig_start_row), 12),

            ('TOPPADDING', (0, sig_start_row + 1), (-1, sig_start_row + 1), 22),

            ('BOTTOMPADDING', (0, sig_start_row + 1), (-1, sig_start_row + 1), 4),

        ])

    return TableStyle(style_cmds)





def _append_signature_rows(table_data, meta_style, col_count=FICHE_COL_COUNT):

    sig_right = ParagraphStyle(

        'FicheCotationSigRight',

        parent=meta_style,

        alignment=TA_RIGHT,

        fontSize=9,

    )

    sig_center = ParagraphStyle(

        'FicheCotationSig',

        parent=meta_style,

        alignment=TA_CENTER,

        fontSize=9,

    )

    empty_cells = [''] * (col_count - 1)

    table_data.append([

        Paragraph(f'Fait à Kinshasa, le {date.today().strftime("%d/%m/%Y")}', sig_right),

        *empty_cells,

    ])

    table_data.append([

        Paragraph('Titulaire de cours', sig_center),

        *empty_cells,

    ])

    return len(table_data) - 2





def _draw_fiche_footer(canvas, doc):

    canvas.saveState()

    canvas.setFont('Helvetica', 8)

    canvas.setFillColor(colors.HexColor('#64748b'))

    canvas.drawCentredString(A4[0] / 2, 0.75 * cm, f'Page {canvas.getPageNumber()}')

    canvas.restoreState()





def libelle_enseignant_ec(ec):
    """Nom affiché de l'enseignant rattaché à l'EC."""
    professeur = getattr(ec, 'professeur', None)
    if professeur:
        nom = f'{professeur.last_name} {professeur.first_name}'.strip()
        if nom:
            return nom
    return '—'


def build_fiche_cotation_pdf(

    *,

    annee,

    session,

    classe,

    ec,

    etudiants,

    lignes_cotation=None,

    avec_notes=False,

):

    buffer = BytesIO()

    doc = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=1.2 * cm,

        leftMargin=1.2 * cm,

        topMargin=1.2 * cm,

        bottomMargin=1.4 * cm,

    )



    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(

        'FicheCotationTitle',

        parent=styles['Title'],

        fontName='Helvetica-Bold',

        fontSize=13,

        leading=15,

        alignment=TA_CENTER,

        textColor=colors.HexColor('#0c4a6e'),

        spaceAfter=4,

    )

    meta_style = ParagraphStyle(

        'FicheCotationMeta',

        parent=styles['Normal'],

        fontName='Helvetica',

        fontSize=8.5,

        leading=10,

        alignment=TA_LEFT,

        textColor=colors.HexColor('#334155'),

    )

    cell_font = 8
    cell_leading = 8 if avec_notes else 9

    cell_style = ParagraphStyle(

        'FicheCotationCell',

        parent=styles['Normal'],

        fontName='Helvetica',

        fontSize=cell_font,

        leading=cell_leading,

        alignment=TA_CENTER,

    )

    cell_left = ParagraphStyle(

        'FicheCotationCellLeft',

        parent=cell_style,

        alignment=TA_LEFT,

        spaceBefore=0,

        spaceAfter=0,

        leading=cell_leading,

    )

    header_cell = ParagraphStyle(

        'FicheCotationHeader',

        parent=cell_style,

        fontName='Helvetica-Bold',

        textColor=colors.white,

        fontSize=cell_font,

        leading=cell_leading + 1,

    )



    promotion = classe.promotion

    filiere = promotion.filiere

    section = filiere.section if filiere else None

    section_label = (

        f'SECTION {section.nom.upper()}'

        if section and section.nom

        else 'SECTION MASTER'

    )



    story = [
        _build_pdf_header(
            annee,
            section_label,
            meta_style,
            qr_payload=_fiche_cotation_qr_payload(session=session, classe=classe, ec=ec),
        ),
        Spacer(1, 0.25 * cm),

        Paragraph('<u><b>FICHE DE COTATION</b></u>', title_style),

        Spacer(1, 0.2 * cm),

    ]



    meta_compact = ParagraphStyle(

        'FicheCotationMetaCompact',

        parent=meta_style,

        fontSize=7.5,

        leading=9,

    )



    session_label = session.code

    if session.nom and session.nom.lower() not in session.code.lower():

        session_label = f'{session.code} ({session.nom})'



    filiere_code = filiere.code if filiere else '—'

    ec_label = f'{ec.code} — {ec.nom}'

    if ec.ue_id and ec.ue.code != ec.code:

        ec_label = f'{ec.ue.code} / {ec.code} — {ec.nom}'



    meta_rows = [

        [

            Paragraph(f'<b>Session</b> {session_label}', meta_compact),

            Paragraph(

                f'<b>Classe</b> {classe.code} — {promotion.nom}'

                f' &nbsp;|&nbsp; <b>Filière</b> {filiere_code}',

                meta_compact,

            ),

        ],

        [

            Paragraph(f'<b>EC</b> {ec_label}', meta_compact),

            Paragraph(

                f'<b>Enseignant</b> {libelle_enseignant_ec(ec)}',

                meta_compact,

            ),

        ],

    ]

    meta_table = Table(meta_rows, colWidths=[8.5 * cm, 8.5 * cm])

    meta_table.setStyle(TableStyle([

        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),

        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#cbd5e1')),

        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),

        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        ('TOPPADDING', (0, 0), (-1, -1), 3),

        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

        ('LEFTPADDING', (0, 0), (-1, -1), 4),

        ('RIGHTPADDING', (0, 0), (-1, -1), 4),

    ]))

    story.append(meta_table)

    story.append(Spacer(1, 0.25 * cm))



    table_data = [[

        Paragraph('<b>N°</b>', header_cell),

        Paragraph('<b>NOM - POSTNOM - PRÉNOM</b>', header_cell),

        Paragraph('<b>TJ/10</b>', header_cell),

        Paragraph('<b>EXAM/10</b>', header_cell),

    ]]



    notes_par_etudiant = {}
    if lignes_cotation:
        for ligne in lignes_cotation:
            notes_par_etudiant[ligne['etudiant'].pk] = ligne



    vide_note = NOTE_MANQUANTE if avec_notes else CELLULE_NOTE_VIDE



    for index, etudiant in enumerate(etudiants, start=1):

        ligne = notes_par_etudiant.get(etudiant.pk)

        tj_cell = _format_note_pdf(ligne['tj'] if ligne else None, vide=vide_note)

        exam_cell = _format_note_pdf(ligne['exam'] if ligne else None, vide=vide_note)

        table_data.append([

            Paragraph(str(index), cell_style),

            Paragraph(etudiant.identite_cotation, cell_left),

            Paragraph(tj_cell, cell_style),

            Paragraph(exam_cell, cell_style),

        ])



    if len(table_data) == 1:

        table_data.append([

            Paragraph('—', cell_style),

            Paragraph('Aucun étudiant inscrit', cell_left),

            Paragraph('', cell_style),

            Paragraph('', cell_style),

        ])



    col_widths = [0.8 * cm, 11.6 * cm, 2.3 * cm, 2.3 * cm]

    sig_start = _append_signature_rows(table_data, meta_style)

    notes_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    notes_table.setStyle(_notes_table_style(sig_start_row=sig_start, compact=avec_notes))

    story.append(notes_table)



    doc.build(story, onFirstPage=_draw_fiche_footer, onLaterPages=_draw_fiche_footer)

    buffer.seek(0)

    return buffer

