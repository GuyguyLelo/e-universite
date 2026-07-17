"""
Services de génération de documents PDF avec ReportLab
"""
import os
import re
import zipfile
from io import BytesIO
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Count
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    Image as RLImage, Flowable as RLFlowable,
)
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from datetime import date, datetime
from decimal import Decimal

from students.models import Student, Inscription
from academics.models import Semestre, UniteEnseignement, ElementConstitutif
from evaluations.models import Session, Note, NoteEC, NoteUE
from deliberations.models import Deliberation, DecisionJury
from deliberations.services import DeliberationEngine
from documents.attestation_pdf import (
    AttestationGenerator,
    INSTITUTION_NOM,
    INSTITUTION_SIGLE,
    build_attestation_filename,
)


def _draw_page_number_footer(canvas, doc):
    """Numéro de page centré en pied de page."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#64748b'))
    page_w = doc.pagesize[0]
    canvas.drawCentredString(page_w / 2, 0.75 * cm, f'Page {canvas.getPageNumber()}')
    canvas.restoreState()


_DECISION_SIGLES = {
    'admis': 'ADM',
    'admis_compensation': 'COMP',
    'admis_avec_dettes': 'ADM-D',
    'defaillant': 'DEF',
    'ajourne': 'AJ',
    'redouble': 'RED',
    'exclu': 'EXC',
    'report': 'REP',
}

_DECISION_LIBELLES_RELEVE = {
    'admis': 'Admis',
    'admis_compensation': 'Admis par compensation',
    'admis_avec_dettes': 'Admis avec dettes',
    'defaillant': 'Défaillant',
    'redouble': 'Redouble',
    'exclu': 'Exclu',
    'ajourne': 'Ajourné',
    'report': 'Report',
}


def _decision_label_releve(decision, jury_label=None):
    """Libellé décision relevé : texte + sigle grille entre parenthèses."""
    if not decision:
        return jury_label or '-'
    label = jury_label or _DECISION_LIBELLES_RELEVE.get(decision, decision)
    sigle = _DECISION_SIGLES.get(decision)
    if sigle and f'({sigle})' not in label:
        return f'{label} ({sigle})'
    return label


def _nom_etudiant_releve_fichier(etudiant) -> str:
    """Nom complet fichier : NOM_POSTNOM_PRENOM."""
    nom = (etudiant.identite_cotation or '').strip().upper()
    nom = re.sub(r'\s*-\s*', '_', nom)
    nom = re.sub(r'\s+', '_', nom)
    nom = re.sub(r'[^\w\-]', '', nom, flags=re.UNICODE)
    return nom or 'ETUDIANT'


def build_releve_notes_filename(etudiant, session_code, filiere_code) -> str:
    """Nom PDF relevé : nom complet + session + filière (ex. NOM_PRENOM_S7-S1_CSI.pdf)."""
    parts = [_nom_etudiant_releve_fichier(etudiant)]
    if session_code:
        parts.append(str(session_code).replace('/', '-'))
    if filiere_code:
        parts.append(str(filiere_code).upper())
    return '_'.join(parts) + '.pdf'


def generer_releve_notes_pdf_bytes(etudiant, semestre, filiere, promotion, annee_academique):
    """Génère le PDF relevé et retourne (bytes, nom_fichier)."""
    buffer = BytesIO()
    generator = ReleveNotesGenerator(
        etudiant, semestre, filiere, promotion, annee_academique, buffer,
    )
    generator.generate()
    session = generator._session_effective()
    session_code = session.code if session else semestre.code
    filiere_code = filiere.code if filiere else ''
    filename = build_releve_notes_filename(etudiant, session_code, filiere_code)
    return buffer.getvalue(), filename


def generer_releves_notes_zip(inscriptions, semestre, filiere, promotion, annee_academique):
    """Génère une archive ZIP de tous les relevés de la promotion."""
    zip_buffer = BytesIO()
    used_names = set()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for ins in inscriptions:
            pdf_bytes, filename = generer_releve_notes_pdf_bytes(
                ins.etudiant, semestre, filiere, promotion, annee_academique,
            )
            unique_name = filename
            counter = 2
            stem, ext = os.path.splitext(filename)
            while unique_name in used_names:
                unique_name = f'{stem}_{counter}{ext}'
                counter += 1
            used_names.add(unique_name)
            archive.writestr(unique_name, pdf_bytes)
    zip_buffer.seek(0)
    zip_name = f'releves_{semestre.code}_{filiere.code}_{promotion.code}.zip'
    return zip_buffer.getvalue(), zip_name


class PDFGenerator:
    """Classe de base pour la génération de documents PDF"""
    
    def __init__(self, buffer=None):
        self.buffer = buffer if buffer else BytesIO()
        self.width, self.height = A4
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Configure les styles personnalisés"""
        # Style titre principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Style sous-titre
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Style normal centré
        self.styles.add(ParagraphStyle(
            name='NormalCenter',
            parent=self.styles['Normal'],
            alignment=TA_CENTER,
            fontSize=10
        ))
        
        # Style normal justifié
        self.styles.add(ParagraphStyle(
            name='NormalJustify',
            parent=self.styles['Normal'],
            alignment=TA_JUSTIFY,
            fontSize=10
        ))
        
        # Style pour les en-têtes de tableau
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))
        
        # Style pour les cellules de tableau
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER
        ))


class ReleveNotesGenerator(PDFGenerator):
    """Générateur de relevés de notes — mise en page aérée, pagination si besoin."""

    MARGIN_LR = 1.5 * cm
    MARGIN_TB = 1.2 * cm
    PAGE_HEIGHT = A4[1]
    SECTION_GAP = 0.35 * cm
    ROW_LINE_EXTRA = 11
    ROW_LINE_MAX_EXTRA = 16
    FOOTER_ROW_COUNT = 3
    SIGNATURE_ZONE = 65
    SIGNATURE_GAP = 0.9 * cm
    LOGO_HEIGHT = 14 * mm
    LOGO_GAP = 3 * mm

    def __init__(self, etudiant, semestre, filiere, promotion, annee_academique, buffer=None):
        super().__init__(buffer)
        self.etudiant = etudiant
        self.semestre = semestre
        self.filiere = filiere
        self.promotion = promotion
        self.annee_academique = annee_academique
        self.session = semestre.sessions.filter(active=True).first()
        self.inscription = Inscription.objects.filter(
            etudiant=etudiant,
            classe__promotion=promotion,
            annee_academique=annee_academique,
        ).first()
        self.content_width = self.width - 2 * self.MARGIN_LR
        self.ec_count = ElementConstitutif.objects.filter(
            ue__semestre=semestre,
            active=True,
        ).count()
        self.body_font = self._body_font_size()
        self.header_font = self.body_font + 1
        self.title_font = min(14, self.body_font + 4)
        self.institution_font = max(self.body_font + 1, 10)

    def _body_font_size(self):
        if self.ec_count <= 14:
            return 9
        if self.ec_count <= 22:
            return 8.5
        if self.ec_count <= 30:
            return 8
        return 7.5

    def _col_widths(self, ratios):
        total = sum(ratios)
        return [self.content_width * ratio / total for ratio in ratios]

    def _fixed_row_height(self):
        return self.body_font + self.ROW_LINE_MAX_EXTRA

    def _first_page_table_y(self):
        y = self.PAGE_HEIGHT - self.MARGIN_TB
        y -= self._header_logo_offset()
        y -= self.institution_font + 6
        y -= self.institution_font + 6  # SECTION MASTER
        y -= self.institution_font + 6  # ANNEE ACADEMIQUE
        y -= self.title_font + 6  # RELEVE DE NOTES (SESSION …)
        y -= self.SECTION_GAP
        line_leading = self.body_font + 6
        box_h = 2 * line_leading + 12
        y -= box_h
        y -= self.SECTION_GAP
        return y

    def _continuation_page_table_y(self):
        y = self.PAGE_HEIGHT - self.MARGIN_TB
        y -= self.body_font + 10
        y -= 0.2 * cm
        return y

    def _max_body_rows_for_page(self, y_top, row_h, with_footers=False):
        page_bottom = self.MARGIN_TB + 14
        if with_footers:
            page_bottom += self.SIGNATURE_ZONE
        available = y_top - page_bottom
        total_rows = int(available // row_h)
        reserved = 1 + (self.FOOTER_ROW_COUNT if with_footers else 0)
        return max(1, total_rows - reserved)

    def _paginate_notes(self, data):
        header = data[0]
        footers = data[-self.FOOTER_ROW_COUNT:]
        body = list(data[1:-self.FOOTER_ROW_COUNT])
        row_h = self._fixed_row_height()
        pages = []
        first = True

        while body:
            y_top = self._first_page_table_y() if first else self._continuation_page_table_y()
            max_with_footer = self._max_body_rows_for_page(y_top, row_h, with_footers=True)
            max_without = self._max_body_rows_for_page(y_top, row_h, with_footers=False)

            if len(body) <= max_with_footer:
                pages.append({
                    'rows': [header] + body + footers,
                    'is_last': True,
                    'is_first': first,
                    'footer_count': self.FOOTER_ROW_COUNT,
                })
                body = []
            else:
                chunk = body[:max_without]
                body = body[max_without:]
                pages.append({
                    'rows': [header] + chunk,
                    'is_last': False,
                    'is_first': first,
                    'footer_count': 0,
                })
            first = False

        if not pages:
            pages.append({
                'rows': [header] + footers,
                'is_last': True,
                'is_first': True,
                'footer_count': self.FOOTER_ROW_COUNT,
            })
        return pages

    def generate(self):
        from reportlab.pdfgen import canvas as pdf_canvas

        c = pdf_canvas.Canvas(self.buffer, pagesize=A4)
        width, _height = A4
        x = self.MARGIN_LR
        data = self._collect_notes_data()
        row_h = self._fixed_row_height()
        pages = self._paginate_notes(data)

        for page_num, page in enumerate(pages):
            if page_num > 0:
                c.showPage()
            y = self.PAGE_HEIGHT - self.MARGIN_TB

            if page['is_first']:
                y = self._draw_canvas_header(c, width, y)
                y -= self.SECTION_GAP
                y = self._draw_canvas_student(c, x, y)
                y -= self.SECTION_GAP
            else:
                y = self._draw_canvas_continuation_header(c, width, y)
                y -= 0.25 * cm

            y = self._draw_canvas_notes_table(
                c, x, y, page['rows'], row_h=row_h, footer_count=page['footer_count'],
            )

            if page['is_last']:
                y -= self.SIGNATURE_GAP
                self._draw_canvas_signatures(c, width, y)

            c.setFont('Helvetica', 8)
            c.setFillColor(colors.HexColor('#64748b'))
            c.drawCentredString(width / 2, 0.75 * cm, f'Page {page_num + 1}')

        c.save()
        return self.buffer

    def _logo_path(self):
        path = _pv_find_logo_path()
        if path:
            return path
        base = str(settings.BASE_DIR)
        for parts in (
            ('documents', 'assets', 'logoeifi.png'),
            ('assets', 'images', 'logoeifi.png'),
        ):
            candidate = os.path.join(base, *parts)
            if os.path.exists(candidate):
                return candidate
        return None

    def _header_logo_offset(self):
        return self.LOGO_HEIGHT + self.LOGO_GAP if self._logo_path() else 0

    def _draw_canvas_logo(self, c, width, y):
        path = self._logo_path()
        if not path:
            return y
        logo_h = self.LOGO_HEIGHT
        cx = width / 2
        c.drawImage(
            path,
            cx - logo_h * 0.5,
            y - logo_h,
            width=logo_h,
            height=logo_h,
            preserveAspectRatio=True,
            mask='auto',
        )
        return y - logo_h - self.LOGO_GAP

    def _session_effective(self):
        """Session affichée / utilisée (après délibération si applicable)."""
        session = self.session
        if session is None:
            return None
        grille = GrilleNotesGenerator(
            self.semestre,
            self.filiere,
            self.promotion,
            self.annee_academique,
            session=session,
        )
        return grille._session_effective_grille(session)

    def _session_label(self):
        """Libellé de session pour l'en-tête (aligné PV / grille)."""
        session = self._session_effective()
        if session is None:
            return '—'
        if session.numero == 2:
            return 'SESSION DE RATTRAPAGE'
        return 'SESSION PRINCIPALE'

    def _section_label(self):
        """Libellé de section pour l'en-tête (aligné PV / grille)."""
        section = getattr(self.filiere, 'section', None) if self.filiere else None
        if section and section.nom:
            return f'SECTION {section.nom.upper()}'
        return 'SECTION MASTER'

    def _draw_canvas_header(self, c, width, y):
        y = self._draw_canvas_logo(c, width, y)
        lines = [
            ("ECOLE INFORMATIQUE DES FINANCES", self.institution_font, True),
            (self._section_label(), self.institution_font, True),
            (
                f"ANNEE ACADEMIQUE {self.annee_academique.code}",
                self.institution_font,
                True,
            ),
            (
                f"RELEVE DE NOTES ({self._session_label()})",
                self.title_font,
                True,
            ),
        ]
        for text, size, bold in lines:
            c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
            c.drawCentredString(width / 2, y, text)
            y -= size + 6
        return y

    def _draw_canvas_continuation_header(self, c, width, y):
        nom, postnom = self._student_nom_postnom()
        prenom = self._format_prenom(self.etudiant.prenom)
        segments = [('RELEVÉ DE NOTES (suite) — ', False), (nom, True)]
        if postnom:
            segments.append((' ' + postnom, True))
        if prenom != '—':
            segments.append((' ' + prenom, True))
        segments.append((f" ({self.etudiant.numero_etudiant})", False))
        self._draw_canvas_centred_segments(c, width, y, segments)
        return y - self.body_font - 4

    def _student_nom_postnom(self):
        nom_raw = (self.etudiant.nom or '').strip()
        tokens = nom_raw.split(None, 1)
        nom = tokens[0] if tokens else '—'
        postnom = tokens[1] if len(tokens) > 1 else ''
        return nom, postnom

    def _format_prenom(self, prenom):
        prenom = (prenom or '').strip()
        if not prenom or prenom == '—':
            return '—'
        if len(prenom) == 1:
            return prenom.upper()
        return prenom[0].upper() + prenom[1:].lower()

    def _promotion_label(self):
        code = (self.promotion.code or '').upper().strip()
        if code == 'PMR':
            return 'PREMIERE ANNEE'
        nom = (self.promotion.nom or '').strip()
        return nom or self.promotion.code or '—'

    def _segment_width(self, c, text, bold=False):
        font = 'Helvetica-Bold' if bold else 'Helvetica'
        return c.stringWidth(text, font, self.body_font)

    def _draw_canvas_text_segments(self, c, x, y, segments):
        cursor = x
        for text, bold in segments:
            font = 'Helvetica-Bold' if bold else 'Helvetica'
            c.setFont(font, self.body_font)
            c.drawString(cursor, y, text)
            cursor += c.stringWidth(text, font, self.body_font)
        return cursor

    def _draw_canvas_centred_segments(self, c, width, y, segments):
        total_w = sum(self._segment_width(c, text, bold) for text, bold in segments)
        self._draw_canvas_text_segments(c, (width - total_w) / 2, y, segments)

    def _draw_canvas_student(self, c, x, y):
        ins = self.inscription
        section = ins.section.nom if ins and ins.section else '—'
        nom, postnom = self._student_nom_postnom()
        prenom = self._format_prenom(self.etudiant.prenom)
        line_y = y - 10 - self.body_font
        line2_y = line_y - (self.body_font + 6)

        line_leading = self.body_font + 6
        padding = 10
        box_h = 2 * line_leading + padding
        c.setStrokeColor(colors.HexColor('#94a3b8'))
        c.setLineWidth(0.5)
        c.rect(x, y - box_h, self.content_width, box_h, stroke=1, fill=0)

        identity_segments = [
            (f"{self.etudiant.numero_etudiant}  |  ", False),
            (nom, True),
        ]
        if postnom:
            identity_segments.append((' ' + postnom, True))
        if prenom != '—':
            identity_segments.append((' ' + prenom, True))
        self._draw_canvas_text_segments(c, x + 8, line_y, identity_segments)

        c.setFont('Helvetica', self.body_font)
        line2 = (
            f"{section}  |  "
            f"{self.filiere.nom}  |  "
            f"{self._promotion_label()}  |  "
            f"{self.semestre.code}"
        )
        c.drawString(x + 8, line2_y, line2[:160])
        return y - box_h

    def _truncate_cell(self, text, col_width):
        value = str(text or '')
        max_chars = max(6, int(col_width / (self.body_font * 0.38)))
        if len(value) > max_chars:
            return value[: max_chars - 1] + '…'
        return value

    def _draw_canvas_notes_table(self, c, x, y, data, row_h=None, footer_count=0):
        col_widths = self._col_widths([4.6, 0.7, 1.15, 0.75, 1.0])
        total_w = sum(col_widths)
        n_rows = len(data)
        if row_h is None:
            row_h = self._fixed_row_height()
        table_bottom = y - row_h * n_rows

        for i, row in enumerate(data):
            top = y - i * row_h
            bottom = top - row_h
            in_footer = footer_count > 0 and i >= n_rows - footer_count
            cells = list(row)
            row_kind = 'body'
            if i > 0 and not in_footer and cells and isinstance(cells[0], str):
                if cells[0].startswith('UE|'):
                    row_kind = 'ue'
                    cells[0] = cells[0][3:]
                elif cells[0].startswith('EC|'):
                    row_kind = 'ec'
                    cells[0] = '    ' + cells[0][3:]

            if i == 0:
                c.setFillColor(colors.HexColor('#1a237e'))
                c.rect(x, bottom, total_w, row_h, stroke=0, fill=1)
                text_color = colors.white
                font = 'Helvetica-Bold'
            elif in_footer:
                c.setFillColor(colors.HexColor('#e8eaf6'))
                c.rect(x, bottom, total_w, row_h, stroke=0, fill=1)
                text_color = colors.black
                font = 'Helvetica-Bold'
            elif row_kind == 'ue':
                c.setFillColor(colors.HexColor('#eef2ff'))
                c.rect(x, bottom, total_w, row_h, stroke=0, fill=1)
                text_color = colors.black
                font = 'Helvetica-Bold'
            elif i % 2 == 0:
                c.setFillColor(colors.HexColor('#f8fafc'))
                c.rect(x, bottom, total_w, row_h, stroke=0, fill=1)
                text_color = colors.black
                font = 'Helvetica'
            else:
                text_color = colors.black
                font = 'Helvetica'

            c.setStrokeColor(colors.HexColor('#cbd5e1'))
            c.setLineWidth(0.4)
            c.rect(x, bottom, total_w, row_h, stroke=1, fill=0)

            x_cell = x
            if footer_count and i >= n_rows - 2:
                c.setFillColor(text_color)
                text_y = bottom + (row_h - self.body_font) / 2
                if row[0] in {'Résultat', 'Synthèse'}:
                    cursor = x + 4
                    c.setFont('Helvetica-Bold', self.body_font)
                    prefix = f"{row[0]} : "
                    c.drawString(cursor, text_y, prefix)
                    cursor += c.stringWidth(prefix, 'Helvetica-Bold', self.body_font)
                    segments = row[1] if isinstance(row[1], list) else [(str(row[1]), False)]
                    for text, bold in segments:
                        font_seg = 'Helvetica-Bold' if bold else 'Helvetica'
                        c.setFont(font_seg, self.body_font)
                        c.drawString(cursor, text_y, text)
                        cursor += c.stringWidth(text, font_seg, self.body_font)
                else:
                    c.setFont(font, self.body_font)
                    label = self._truncate_cell(row[0], col_widths[0])
                    c.drawString(x + 4, text_y, label)
                    span_text = self._truncate_cell(row[1], sum(col_widths[1:]))
                    c.drawString(x + col_widths[0] + 4, text_y, span_text)
                continue

            for j, cell in enumerate(cells):
                c.setFillColor(text_color)
                cell_font = 'Helvetica-Bold' if j >= 1 else font
                c.setFont(cell_font, self.body_font)
                text = self._truncate_cell(cell, col_widths[j])
                align_x = x_cell + 4
                if j >= 1:
                    align_x = x_cell + (col_widths[j] - c.stringWidth(text, cell_font, self.body_font)) / 2
                c.drawString(align_x, bottom + (row_h - self.body_font) / 2, text)
                x_cell += col_widths[j]
                c.line(x_cell, bottom, x_cell, top)
        return table_bottom

    def _draw_canvas_signatures(self, c, width, y):
        """Date à droite, Secrétaire du Jury (gauche) et Président du Jury (droite)."""
        x_left = self.MARGIN_LR
        x_right = width - self.MARGIN_LR
        c.setFillColor(colors.black)
        c.setFont('Helvetica', self.body_font)
        c.drawRightString(
            x_right,
            y,
            f"Fait à Kinshasa, le {datetime.now().strftime('%d/%m/%Y')}",
        )
        y -= self.body_font + 14
        c.setFont('Helvetica-Bold', self.body_font)
        c.drawString(x_left, y, 'Secrétaire du Jury')
        c.drawRightString(x_right, y, 'Président du Jury')
        return y

    @staticmethod
    def _ue_solo_pour_releve(ue, ecs):
        """UE sans EC, ou un seul EC miroir (même code) : une seule ligne au relevé."""
        if not ecs:
            return True
        return len(ecs) == 1 and ecs[0].code == ue.code

    def _collect_notes_data(self):
        grille = GrilleNotesGenerator(
            self.semestre,
            self.filiere,
            self.promotion,
            self.annee_academique,
            session=self.session,
        )
        ues, all_ecs, all_ue_solos = grille._structure_semestre_filiere()
        row = grille.construire_ligne_etudiant(self.etudiant, all_ecs, all_ue_solos)

        session_grille = grille._session_effective_grille(self.session)
        engine = DeliberationEngine(session_grille, self.promotion) if session_grille else None

        header = ['UE / EC', 'Cat.', 'NOTE/20', 'Cr.', 'Note pond.']
        data = [header]

        total_credits_cap = 0
        for ue in ues:
            ecs = list(ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code'))
            cat = ue.categorie or 'A'
            if self._ue_solo_pour_releve(ue, ecs):
                if ecs:
                    ec = ecs[0]
                    note = row['notes_ec'].get(ec.id)
                    cr_max = int(ec.credits_ects or ue.credits_ects or 0)
                    credit_cap = row['credits_ec'].get(ec.id)
                else:
                    note = row['notes_ue'].get(ue.id)
                    cr_max = int(ue.credits_ects or 0)
                    credit_cap = GrilleNotesGenerator._credit_capitalise_ue_solo(
                        row, ue, engine, all_ecs, all_ue_solos,
                    )
                if credit_cap is not None:
                    total_credits_cap += int(credit_cap)
                data.append([
                    f'UE|{ue.code} — {ue.nom}',
                    cat,
                    f'{note:.2f}' if note is not None else '-',
                    GrilleNotesGenerator._fmt_credit_grille(credit_cap),
                    (
                        f'{(Decimal(str(note)) * Decimal(str(cr_max))).quantize(Decimal("0.01"))}'
                        if note is not None else '-'
                    ),
                ])
                continue

            data.append([f'UE|{ue.code} — {ue.nom}', '', '', '', ''])

            for ec in ecs:
                note = row['notes_ec'].get(ec.id)
                credit_cap = row['credits_ec'].get(ec.id)
                cr_max = int(ec.credits_ects or 0)
                if credit_cap is not None:
                    total_credits_cap += int(credit_cap)
                data.append([
                    f'EC|{ec.code} — {ec.nom}',
                    cat,
                    f'{note:.2f}' if note is not None else '-',
                    GrilleNotesGenerator._fmt_credit_grille(credit_cap),
                    (
                        f'{(Decimal(str(note)) * Decimal(str(cr_max))).quantize(Decimal("0.01"))}'
                        if note is not None else '-'
                    ),
                ])

        dec = row.get('decision') or ''
        dec_label = _decision_label_releve(dec, row.get('decision_label'))
        moy_s = row.get('moy_semestre')
        co = row.get('credit_semestre')
        np_total = row.get('note_ponderee')

        data.append([
            'Total',
            '',
            '',
            str(total_credits_cap),
            str(np_total) if np_total is not None else '-',
        ])
        if moy_s is not None and row.get('moy_a') is not None and row.get('moy_b') is not None:
            synth = [
                ('Moy.A ', True),
                (f"{row['moy_a']:.2f}", False),
                (' · ', False),
                ('Moy.B ', True),
                (f"{row['moy_b']:.2f}", False),
                (' · ', False),
                ('Moy. ', True),
                (f"{moy_s:.2f}", False),
            ]
        else:
            synth = [('—', False)]
        data.append(['Synthèse', synth, '', '', ''])
        mention = self._compute_mention(moy_s)
        co_txt = str(co) if co is not None else '-'
        data.append([
            'Résultat',
            [
                ('Crédits capitalisés : ', True),
                (co_txt, False),
                (' · ', False),
                ('Décision : ', True),
                (dec_label, False),
                (' · ', False),
                ('Mention : ', True),
                (mention, False),
            ],
            '', '', '',
        ])
        return data

    def _decision_label(self, decision):
        return _decision_label_releve(decision)

    def _compute_mention(self, moyenne):
        if moyenne is None: return '-'
        if moyenne >= 16: return 'Très Bien'
        if moyenne >= 14: return 'Bien'
        if moyenne >= 12: return 'Assez Bien'
        if moyenne >= 10: return 'Passable'
        return 'Insuffisant'


_MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
)
_PV_COLOR_PRIMARY = colors.HexColor('#0369A1')
_PV_COLOR_MUTED = colors.HexColor('#64748B')
_PV_COLOR_INK = colors.HexColor('#1E293B')
_PV_LIEU_DEFAUT = 'Kinshasa'

_UNITE_FR = {
    0: 'zéro', 1: 'un', 2: 'deux', 3: 'trois', 4: 'quatre', 5: 'cinq', 6: 'six',
    7: 'sept', 8: 'huit', 9: 'neuf', 10: 'dix', 11: 'onze', 12: 'douze',
    13: 'treize', 14: 'quatorze', 15: 'quinze', 16: 'seize', 17: 'dix-sept',
    18: 'dix-huit', 19: 'dix-neuf',
}
_DIZAINE_FR = {
    2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante',
    7: 'soixante', 8: 'quatre-vingt', 9: 'quatre-vingt',
}


def _nombre_en_lettres_fr(n: int) -> str:
    """Convertit un entier (0–99) en toutes lettres (français)."""
    if n < 20:
        return _UNITE_FR[n]
    if n < 70:
        diz, uni = divmod(n, 10)
        base = _DIZAINE_FR[diz]
        if uni == 1 and diz != 8:
            return f'{base} et un'
        if uni:
            liaison = '-' if diz != 8 else '-'
            return f'{base}{liaison}{_UNITE_FR[uni]}'
        return base
    if n < 80:
        return f'soixante-{_nombre_en_lettres_fr(n - 60)}'
    if n < 100:
        if n == 80:
            return 'quatre-vingts'
        return f'quatre-vingt-{_nombre_en_lettres_fr(n - 80)}'
    return str(n)


def _annee_en_lettres_fr(year: int) -> str:
    if 2000 <= year < 2100:
        reste = year - 2000
        if reste == 0:
            return 'deux mille'
        return f'deux mille {_nombre_en_lettres_fr(reste)}'
    return str(year)


def _jour_en_lettres_fr(day: int) -> str:
    if day == 1:
        return 'premier'
    return _nombre_en_lettres_fr(day)


def _pv_find_logo_path():
    base = str(settings.BASE_DIR)
    for parts in (
        ('static', 'images', 'logoeifi.png'),
        ('static', 'image', 'logoeifi.png'),
        ('media', 'logoeifi.png'),
        ('documents', 'assets', 'logoeifi.png'),
        ('assets', 'images', 'logoeifi.png'),
    ):
        path = os.path.join(base, *parts)
        if os.path.exists(path):
            return path
    return None


def _pv_logo_flowable(path, width_mm=18):
    if not path:
        return None
    img = RLImage(path)
    img.drawHeight = width_mm * mm * img.drawHeight / img.drawWidth
    img.drawWidth = width_mm * mm
    return img


def _annee_academique_libelle(deliberation, session) -> str:
    if deliberation.annee_academique_id:
        return deliberation.annee_academique.code
    if session and getattr(session, 'annee_academique', None):
        return session.annee_academique.code
    return '—'


def _niveau_pedagogique(promotion) -> str:
    code = (promotion.code or '').upper().strip()
    for niveau in ('L1', 'L2', 'L3', 'M1', 'M2'):
        if code == niveau or code.startswith(f'{niveau}-') or code.startswith(f'{niveau}_'):
            return niveau
    filiere = getattr(promotion, 'filiere', None)
    section = getattr(filiere, 'section', None) if filiere else None
    section_code = (getattr(section, 'code', '') or '').upper()
    ordre = promotion.ordre or 1
    if 'MASTER' in section_code or section_code in ('M', 'MAS'):
        return f'M{min(ordre, 2)}'
    return f'L{min(ordre, 3)}'


def _effectif_etudiants_fr(n: int) -> str:
    if n == 0:
        return 'aucun étudiant'
    if n == 1:
        return '1 étudiant'
    return f'{n} étudiants'


def _semestre_pv_libelle(deliberation, semestre) -> str:
    if deliberation.type_deliberation == deliberation.TYPE_ANNUELLE:
        s1 = deliberation.semestre1.code if deliberation.semestre1_id else 'S1'
        s2 = deliberation.semestre2.code if deliberation.semestre2_id else 'S2'
        return f'{s1} et {s2}'
    if deliberation.type_deliberation == deliberation.TYPE_CYCLE_MASTER:
        return 'cycle Master (M1 et M2)'
    if semestre:
        return semestre.code
    return '—'


def _semestre_pv_numero(deliberation, semestre) -> str:
    """Libellé « semestre 5 » / « semestres S7 et S8 » pour le corps du PV."""
    if deliberation.type_deliberation == deliberation.TYPE_ANNUELLE:
        s1 = deliberation.semestre1.numero if deliberation.semestre1_id else 1
        s2 = deliberation.semestre2.numero if deliberation.semestre2_id else 2
        return f'semestres {s1} et {s2}'
    if deliberation.type_deliberation == deliberation.TYPE_CYCLE_MASTER:
        return 'cycle Master'
    if semestre and semestre.numero:
        return f'semestre {semestre.numero}'
    if semestre and semestre.code:
        return f'semestre {semestre.code.lstrip("Ss")}'
    return 'semestre'


def _annee_academique_pv_affiche(deliberation, session) -> str:
    """Format « 2025 - 2026 » pour le titre et le corps du PV."""
    code = _annee_academique_libelle(deliberation, session)
    if not code or code == '—':
        return '—'
    return code.replace('-', ' - ').replace('  -  ', ' - ')


def _cohorte_pv_libelle(promotion) -> str:
    """Ex. « L3 LMD- AP », « M1 LMD- RX »."""
    niveau = _niveau_pedagogique(promotion)
    filiere = getattr(promotion, 'filiere', None)
    filiere_code = (getattr(filiere, 'code', '') or '').strip().upper()
    if filiere_code:
        return f'{niveau} LMD- {filiere_code}'
    return f'{niveau} LMD'


def _credits_semestre_pv(deliberation) -> int:
    """
    Crédits du semestre à capitaliser (ex. 30), pas le seuil de passage annuel.
    Priorité : crédits_totaux des décisions, puis somme des UE du semestre.
    """
    from django.db.models import Count
    from academics.models import UniteEnseignement

    if deliberation:
        row = (
            DecisionJury.objects.filter(
                deliberation=deliberation,
                credits_totaux__isnull=False,
            )
            .values('credits_totaux')
            .annotate(n=Count('id'))
            .order_by('-n')
            .first()
        )
        if row and row['credits_totaux']:
            return int(row['credits_totaux'])

    semestre = None
    filiere = None
    if deliberation:
        session = getattr(deliberation, 'session', None)
        if session:
            semestre = session.semestre
        promotion = getattr(deliberation, 'promotion', None)
        if promotion:
            filiere = getattr(promotion, 'filiere', None)

    if semestre:
        qs = UniteEnseignement.objects.filter(semestre=semestre, active=True)
        if filiere:
            qs = qs.filter(filiere=filiere)
        total = sum((ue.credits_ects or 0) for ue in qs)
        if total:
            return int(total)

    return 30


def _candidats_effectif_fr(n: int) -> str:
    if n <= 0:
        return '0 candidat'
    if n == 1:
        return '1 candidat'
    return f'{n} candidats'


class ProcesVerbalGenerator(PDFGenerator):
    """Générateur de procès-verbal de délibération — modèle LMD institutionnel."""

    def __init__(self, deliberation, buffer=None):
        super().__init__(buffer)
        self.deliberation = deliberation
        self.session = deliberation.session
        self.semestre = self.session.semestre if self.session else None
        self.promotion = self.deliberation.promotion
        self._setup_pv_styles()

    def _setup_pv_styles(self):
        self.styles.add(ParagraphStyle(
            name='PVInstitution',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=12,
            textColor=_PV_COLOR_PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=2,
        ))
        self.styles.add(ParagraphStyle(
            name='PVInstitutionSub',
            parent=self.styles['Normal'],
            fontSize=8.5,
            leading=11,
            textColor=_PV_COLOR_MUTED,
            alignment=TA_CENTER,
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            name='PVDocTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=_PV_COLOR_INK,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name='PVDocSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=_PV_COLOR_INK,
            alignment=TA_CENTER,
            spaceAfter=16,
        ))
        self.styles.add(ParagraphStyle(
            name='PVBody',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=15,
            textColor=_PV_COLOR_INK,
            alignment=TA_JUSTIFY,
            firstLineIndent=1.0 * cm,
            spaceAfter=10,
        ))
        self.styles.add(ParagraphStyle(
            name='PVBodyNoIndent',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=_PV_COLOR_INK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name='PVDecision',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=15,
            textColor=_PV_COLOR_INK,
            alignment=TA_JUSTIFY,
            firstLineIndent=0,
            spaceAfter=8,
        ))
        self.styles.add(ParagraphStyle(
            name='PVBullet',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=_PV_COLOR_INK,
            alignment=TA_JUSTIFY,
            leftIndent=1.2 * cm,
            bulletIndent=0.5 * cm,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name='PVClosing',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=_PV_COLOR_INK,
            alignment=TA_JUSTIFY,
            firstLineIndent=1.0 * cm,
            spaceBefore=6,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name='PVSignatureTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name='PVSignature',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=2,
        ))

    def _pv_body(self, text: str) -> Paragraph:
        return Paragraph(text, self.styles['PVBody'])

    def _pv_decision(self, text: str) -> Paragraph:
        return Paragraph(text, self.styles['PVDecision'])

    def generate(self):
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2.2 * cm,
            leftMargin=2.2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        story = []
        story.extend(self._build_header())
        story.extend(self._build_ouverture())
        story.extend(self._build_decisions())
        if self.deliberation.notes:
            story.append(self._pv_body(
                f'<i>Observations du jury :</i> {self.deliberation.notes}'
            ))
        story.extend(self._build_cloture())
        story.extend(self._build_signatures())
        doc.build(story, onFirstPage=_draw_page_number_footer, onLaterPages=_draw_page_number_footer)
        return self.buffer

    def _pv_section_label(self):
        filiere = getattr(self.promotion, 'filiere', None) if self.promotion else None
        section = getattr(filiere, 'section', None) if filiere else None
        if section and section.nom:
            return f'SECTION {section.nom.upper()}'
        return 'SECTION MASTER'

    def _build_header(self):
        elements = []
        logo = _pv_logo_flowable(_pv_find_logo_path())
        if logo:
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph('ÉCOLE INFORMATIQUE DES FINANCES', self.styles['PVInstitution']))
        elements.append(Paragraph(self._pv_section_label(), self.styles['PVInstitution']))
        elements.append(Paragraph(
            f'{INSTITUTION_SIGLE} — Système Licence-Master-Doctorat (LMD)',
            self.styles['PVInstitutionSub'],
        ))
        semestre_lib = _semestre_pv_numero(self.deliberation, self.semestre).upper()
        annee = _annee_academique_pv_affiche(self.deliberation, self.session)
        session_lib = 'SESSION PRINCIPALE'
        if self.session and self.session.numero == 2:
            session_lib = 'SESSION DE RATTRAPAGE'
        elements.append(Paragraph(
            f'PROCES-VERBAL DE DELIBERATION DU {semestre_lib}',
            self.styles['PVDocTitle'],
        ))
        elements.append(Paragraph(
            f'DE L’ANNEE ACADEMIQUE {annee}',
            self.styles['PVDocTitle'],
        ))
        elements.append(Paragraph(
            f'<font size="9">({session_lib})</font>',
            self.styles['PVDocSubtitle'],
        ))
        return elements

    def _build_ouverture(self):
        semestre = _semestre_pv_numero(self.deliberation, self.semestre)
        annee = _annee_academique_pv_affiche(self.deliberation, self.session)
        cohorte = _cohorte_pv_libelle(self.promotion)
        total = sum(self._decision_counts().values())
        effectif = _candidats_effectif_fr(total)
        texte = (
            f'Le jury chargé de l’organisation des épreuves du <b>{semestre}</b> '
            f'des étudiants de <b>{cohorte}</b> de l’année académique <b>{annee}</b> '
            f'a reçu les épreuves de <b>{effectif}</b> pour le {semestre}.'
        )
        return [
            self._pv_body(texte),
            self._pv_body(
                'Après délibération à huis clos ; le jury a pris les décisions suivantes :'
            ),
        ]

    def _decision_counts(self) -> dict:
        counts = {}
        for row in (
            DecisionJury.objects.filter(deliberation=self.deliberation)
            .values('decision')
            .annotate(total=Count('id'))
        ):
            counts[row['decision']] = row['total']
        return counts

    def _build_decisions(self):
        stats = self._decision_counts()
        semestre = _semestre_pv_numero(self.deliberation, self.semestre)
        credits = _credits_semestre_pv(self.deliberation)
        elements = []

        definitions = [
            (
                'admis',
                (
                    f'Sont admis au {semestre}, avec une capitalisation définitive '
                    f'des {credits} crédits, {{n}} dont la décision d’admission est '
                    f'indiquée dans la grille (voir la Décision ADM).'
                ),
            ),
            (
                'admis_compensation',
                (
                    f'Sont admis au {semestre}, avec compensation de notes en '
                    f'capitalisant {credits} crédits, {{n}} dont la décision '
                    f'd’admission est indiquée dans la grille (voir la Décision COMP).'
                ),
            ),
            (
                'defaillant',
                (
                    f'Sont défaillants au {semestre}, {{n}} dont il manque des notes '
                    f'dans la grille (voir la Décision DEF).'
                ),
            ),
            (
                'ajourne',
                (
                    f'Sont ajournés au {semestre}, {{n}} n’ayant pas capitalisé '
                    f'{credits} crédits (voir la Décision AJ).'
                ),
            ),
            (
                'admis_avec_dettes',
                (
                    f'Sont admis au {semestre} avec dettes, {{n}} dont la décision '
                    f'est indiquée dans la grille (voir la Décision ADM-D).'
                ),
            ),
            (
                'redouble',
                (
                    f'Sont autorisés à redoubler le {semestre}, {{n}} '
                    f'(voir la Décision RED).'
                ),
            ),
            (
                'exclu',
                (
                    f'Sont exclus, {{n}} dont la décision est indiquée dans la grille '
                    f'(voir la Décision EXC).'
                ),
            ),
            (
                'report',
                (
                    f'Sont reportés, {{n}} dont la décision est indiquée dans la grille '
                    f'(voir la Décision REP).'
                ),
            ),
        ]

        numero = 0
        for code, modele in definitions:
            n = stats.get(code, 0)
            if n <= 0:
                continue
            numero += 1
            texte = modele.format(n=_candidats_effectif_fr(n))
            elements.append(self._pv_decision(f'<b>{numero}.</b> {texte}'))

        if not elements:
            elements.append(self._pv_body(
                '<i>Aucune décision individuelle n’a encore été enregistrée pour cette séance.</i>'
            ))
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_cloture(self):
        date_style = ParagraphStyle(
            'PVDateLieu',
            parent=self.styles['PVClosing'],
            alignment=TA_RIGHT,
            firstLineIndent=0,
        )
        elements = [
            Paragraph(
                'En foi de quoi, le présent procès-verbal a été dressé pour servir '
                'et valoir ce que de droit.',
                self.styles['PVClosing'],
            ),
            Paragraph(
                f'Fait à {_PV_LIEU_DEFAUT}, le ____________________',
                date_style,
            ),
        ]
        return elements

    def _pv_signature_column(self, title, *, n_lines=1, alignment=TA_CENTER, top_spacer_cm=0):
        parts = []
        if top_spacer_cm:
            parts.append(Spacer(1, top_spacer_cm * cm))
        parts.append(Paragraph(
            f'<b>{title}</b>',
            ParagraphStyle(
                'PVSigColTitle',
                parent=self.styles['PVSignatureTitle'],
                alignment=alignment,
                spaceBefore=0,
                spaceAfter=6,
            ),
        ))
        for i in range(max(n_lines, 1)):
            if i:
                parts.append(Spacer(1, 0.7 * cm))
            else:
                parts.append(Spacer(1, 1.0 * cm))
            parts.append(Paragraph(
                '_________________________',
                ParagraphStyle(
                    'PVSigColLine',
                    parent=self.styles['PVSignature'],
                    alignment=alignment,
                ),
            ))
        return parts

    def _build_signatures(self):
        """Secrétaire à gauche, Membres au centre (légèrement plus bas), Président à droite."""
        col_w = (A4[0] - 2 * 2.2 * cm) / 3.0
        left = self._pv_signature_column(
            'Le Secrétaire du Jury', n_lines=1, alignment=TA_LEFT,
        )
        center = self._pv_signature_column(
            'Les Membres du Jury', n_lines=3, alignment=TA_CENTER, top_spacer_cm=1.2,
        )
        right = self._pv_signature_column(
            'Le Président du Jury', n_lines=1, alignment=TA_RIGHT,
        )
        sig_table = Table(
            [[left, center, right]],
            colWidths=[col_w, col_w, col_w],
        )
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [Spacer(1, 0.6 * cm), sig_table]


def generer_attestation_pdf(attestation, genere_par=None, *, enregistrer=True):
    """Génère le PDF d'une attestation et l'enregistre éventuellement."""
    from django.core.files.base import ContentFile
    from django.utils import timezone
    from documents.models import DocumentGenere, TypeDocumentGenere

    buffer = BytesIO()
    AttestationGenerator(attestation=attestation, buffer=buffer).generate()
    pdf_bytes = buffer.getvalue()
    filename = build_attestation_filename(attestation)

    if enregistrer:
        attestation.fichier.save(filename, ContentFile(pdf_bytes), save=False)
        attestation.date_generation = timezone.now()
        attestation.genere_par = genere_par
        attestation.save(update_fields=['fichier', 'date_generation', 'genere_par', 'updated_at'])

        type_doc, _ = TypeDocumentGenere.objects.get_or_create(
            code=f'ATT_{attestation.type_attestation.code.upper()}',
            defaults={'nom': attestation.type_attestation.nom, 'active': True},
        )
        DocumentGenere.objects.create(
            type_document=type_doc,
            etudiant=attestation.etudiant,
            inscription=attestation.inscription,
            fichier=ContentFile(pdf_bytes, name=filename),
            genere_par=genere_par,
            notes=attestation.numero,
        )

    return pdf_bytes, filename


class RotatedText(RLFlowable):
    """Flowable avec texte tourné (lecture bas→haut) centré dans la cellule."""

    def __init__(self, text, font_name='Helvetica', font_size=8, bold=False, color=None):
        RLFlowable.__init__(self)
        self.text = text
        self.fn = f"{font_name}-Bold" if bold else font_name
        self.fs = font_size
        self.color = color or colors.black

    def wrap(self, availWidth, availHeight):
        self.tw = stringWidth(self.text, self.fn, self.fs)
        self._width = min(self.fs + 4, availWidth)
        self._height = min(self.tw + 4, availHeight)
        return (self._width, self._height)

    def draw(self):
        self.canv.saveState()
        self.canv.translate(self._width * 0.5, self._height * 0.5)
        self.canv.rotate(90)            # texte vers le HAUT (bas→haut)
        self.canv.setFont(self.fn, self.fs)
        self.canv.setFillColor(self.color)
        # drawString : 1er char en bas, dernier en haut
        # Aligné au début (bas) : start = -_height/2
        self.canv.drawString(-self._height * 0.5, -self.fs * 0.3, self.text)
        self.canv.restoreState()


class GrilleNotesGenerator(PDFGenerator):
    """
    Générateur de grille de notes pour le jury (tableau récapitulatif).
    Format paysage A4 – en-têtes UE et EC tournés verticalement.
    """

    WHITE = colors.white
    BLACK = colors.black
    HEADER_BG = colors.HexColor('#f5f5f5')
    CAT_BG = colors.HexColor('#fafafa')
    MAX_BG = colors.white
    UE_HDR_BG = colors.HexColor('#eeeeee')
    SUM_HDR_BG = colors.HexColor('#eeeeee')
    ROW_ALT_BG = colors.HexColor('#fafafa')

    def __init__(self, semestre, filiere, promotion, annee_academique, session=None, deliberation=None, buffer=None):
        super().__init__(buffer)
        self.semestre = semestre
        self.filiere = filiere
        self.promotion = promotion
        self.annee_academique = annee_academique
        self.session = session
        self.deliberation = deliberation
        self._init_styles()

    def _init_styles(self):
        """Styles Paragraph pour la grille."""
        base = self.styles['Normal']
        self.st_cell = ParagraphStyle('gr_cell', parent=base, fontSize=6, leading=9,
                                       spaceBefore=1, spaceAfter=1)
        self.st_cell_b = ParagraphStyle('gr_cell_b', parent=base, fontSize=6, leading=9,
                                        fontName='Helvetica-Bold', spaceBefore=1, spaceAfter=1)
        self.st_cell_w = ParagraphStyle('gr_cell_w', parent=self.st_cell_b,
                                        textColor=colors.HexColor('#1a1a1a'))
        self.st_header = ParagraphStyle('gr_header', parent=self.st_cell_b,
                                        textColor=colors.HexColor('#1a1a1a'))
        self.st_left = ParagraphStyle('gr_left', parent=self.st_cell, alignment=TA_LEFT)
        self.st_left_b = ParagraphStyle('gr_left_b', parent=self.st_cell_b, alignment=TA_LEFT)
        self.st_nom = ParagraphStyle(
            'gr_nom',
            parent=self.st_cell,
            fontSize=6,
            leading=7,
            alignment=TA_LEFT,
            spaceBefore=0,
            spaceAfter=0,
        )
        self.st_num = ParagraphStyle(
            'gr_num',
            parent=self.st_cell,
            fontSize=6,
            leading=7,
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=0,
        )
        self.st_title = ParagraphStyle('gr_title', parent=base, fontSize=9, leading=12,
                                       fontName='Helvetica-Bold', alignment=TA_CENTER,
                                       spaceBefore=1, spaceAfter=1)

    def _grille_semestre_label(self):
        if self.semestre.nom:
            return self.semestre.nom
        return f'Semestre {self.semestre.numero}'

    def _grille_promotion_label(self):
        promo = (self.promotion.nom or self.promotion.code or '').strip()
        filiere_code = (self.filiere.code or '').strip() if self.filiere else ''
        promo_upper = promo.upper()
        filiere_upper = filiere_code.upper()

        if filiere_code and filiere_upper not in promo_upper:
            if 'MASTER' in promo_upper:
                label = f'{promo} {filiere_code}'
            else:
                label = f'{promo} MASTER {filiere_code}'
        else:
            label = promo
        return label.upper()

    def _grille_section_label(self):
        section = getattr(self.filiere, 'section', None) if self.filiere else None
        if section and section.nom:
            return f'SECTION {section.nom.upper()}'
        return 'SECTION MASTER'

    def _build_grille_header(self, content_width):
        from evaluations.pdf import _find_logo_path, _logo_flowable

        logo = _logo_flowable(_find_logo_path(), width_mm=16)
        title_style = ParagraphStyle(
            'gr_title_left',
            parent=self.st_title,
            alignment=TA_LEFT,
            fontSize=9,
            leading=11,
        )
        title_text = (
            f"<b>ECOLE INFORMATIQUE DES FINANCES</b><br/>"
            f"<b>{self._grille_section_label()}</b><br/>"
            f"Grille des Notes — {self._grille_semestre_label()} — {self._grille_promotion_label()} | "
            f"Année acad. {self.annee_academique.code}"
        )
        logo_col = 22 * mm
        text_col = max(content_width - logo_col, content_width * 0.75)
        logo_col = content_width - text_col

        logo_cell = logo if logo else Paragraph(
            'EIFI',
            ParagraphStyle(
                'gr_logo_fallback',
                parent=self.st_title,
                fontName='Helvetica-Bold',
                fontSize=11,
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#0c4a6e'),
            ),
        )
        header = Table(
            [[Paragraph(title_text, title_style), logo_cell]],
            colWidths=[text_col, logo_col],
        )
        header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return header

    def generate(self):
        from reportlab.platypus import SimpleDocTemplate

        buffer = self.buffer
        landscape_w, landscape_h = 842, 595  # A4 paysage (points)
        margin_lr = 1.2 * cm
        content_width = landscape_w - 2 * margin_lr

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(landscape_w, landscape_h),
            rightMargin=1.2*cm,
            leftMargin=1.2*cm,
            topMargin=1.0*cm,
            bottomMargin=1.0*cm,
        )

        data = self._build_grid_data()
        story = []

        story.append(self._build_grille_header(content_width))
        story.append(Spacer(1, 0.3*cm))

        # --- Tableau ---
        table, _ = self._build_table(data)
        story.append(table)
        story.extend(self._build_grille_jury_signatures(content_width))

        doc.build(story, onFirstPage=_draw_page_number_footer, onLaterPages=_draw_page_number_footer)
        return buffer

    def _jury_column_paragraph(self, title, *, alignment=TA_CENTER):
        return Paragraph(
            f'<b>{title}</b>',
            ParagraphStyle(
                'gr_jury_col',
                parent=self.st_cell,
                fontSize=7,
                leading=10,
                alignment=alignment,
            ),
        )

    def _build_grille_jury_signatures(self, content_width):
        """Bloc signatures : Secrétaire, Membres, Président du jury (sans noms)."""
        col_w = content_width / 3.0
        sig_table = Table(
            [[
                self._jury_column_paragraph('SECRÉTAIRES DU JURY', alignment=TA_LEFT),
                self._jury_column_paragraph('MEMBRES DU JURY'),
                self._jury_column_paragraph('PRÉSIDENT DU JURY', alignment=TA_RIGHT),
            ]],
            colWidths=[col_w, col_w, col_w],
        )
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [
            Spacer(1, 0.5 * cm),
            sig_table,
        ]

    def _deliberation_semestrielle(self):
        """Délibération semestrielle terminée pour ce semestre et cette promotion."""
        if (
            self.deliberation
            and self.deliberation.type_deliberation == Deliberation.TYPE_SEMESTRIELLE
            and self.deliberation.statut in ('terminee', 'verrouillee')
            and self.deliberation.session
            and self.deliberation.session.semestre_id == self.semestre.id
            and self.deliberation.promotion_id == self.promotion.id
        ):
            return self.deliberation
        return (
            Deliberation.objects.filter(
                promotion=self.promotion,
                type_deliberation=Deliberation.TYPE_SEMESTRIELLE,
                statut__in=('terminee', 'verrouillee'),
                session__semestre=self.semestre,
            )
            .select_related('session')
            .order_by('-session__numero', '-date_deliberation')
            .first()
        )

    def _session_effective_grille(self, session):
        """
        Session utilisée pour notes et décisions sur la grille.
        Après délibération, utilise la session du jury (souvent S2/rattrapage).
        """
        deliberation = self._deliberation_semestrielle()
        if deliberation:
            return deliberation.session
        return session

    def _decisions_jury_par_etudiant(self):
        """Décisions officielles du jury semestriel (semestre + promotion)."""
        deliberation = self._deliberation_semestrielle()
        if not deliberation:
            return {}
        return {
            d.etudiant_id: d
            for d in DecisionJury.objects.filter(deliberation=deliberation).select_related('etudiant')
        }

    @staticmethod
    def _calculer_note_ponderee(all_ecs, all_ue_solos, notes_ec, notes_ue):
        """
        Note pondérée = Σ(note × crédit ECTS) sur les EC et les UE sans EC.
        Affichée seulement si toutes les notes attendues sont présentes.
        """
        total = Decimal('0.00')
        for ec in all_ecs:
            note = notes_ec.get(ec.id)
            if note is None:
                return None
            total += Decimal(str(note)) * Decimal(str(ec.credits_ects or 0))
        for ue in all_ue_solos:
            note = notes_ue.get(ue.id)
            if note is None:
                return None
            total += Decimal(str(note)) * Decimal(str(ue.credits_ects or 0))
        if not all_ecs and not all_ue_solos:
            return None
        return int(total.quantize(Decimal('1')))

    @staticmethod
    def _a_note_manquante(row, all_ecs, all_ue_solos):
        """True si au moins une note EC / UE solo est vide."""
        for ec in all_ecs:
            if row['notes_ec'].get(ec.id) is None:
                return True
        for ue in all_ue_solos:
            if row['notes_ue'].get(ue.id) is None:
                return True
        return False

    @staticmethod
    def _masquer_synthese_si_note_manquante(row, all_ecs, all_ue_solos):
        """
        Si au moins une note est vide : ne pas afficher note pondérée,
        moy. cat. A/B ni moyenne semestre.
        Crédit total (semestre) jamais affiché pour un défaillant.
        """
        if GrilleNotesGenerator._a_note_manquante(row, all_ecs, all_ue_solos):
            row['note_ponderee'] = None
            row['moy_a'] = None
            row['moy_b'] = None
            row['moy_semestre'] = None
        if row.get('decision') == 'defaillant':
            row['credit_semestre'] = None

    @staticmethod
    def _sans_compensation_defaillant(row, all_ecs, all_ue_solos):
        """Défaillant avec notes incomplètes : pas de compensation, seuil direct seulement."""
        if row.get('decision') != 'defaillant':
            return False
        return GrilleNotesGenerator._a_note_manquante(row, all_ecs, all_ue_solos)

    @staticmethod
    def _remplir_credits_ec(row, all_ecs, engine=None, all_ue_solos=None):
        """
        Crédits capitalisés par EC : note ≥ seuil, ou validation par compensation UE.
        Défaillant avec notes manquantes : pas de compensation (crédit si note ≥ seuil seulement).
        """
        credits_ec = row.setdefault('credits_ec', {})
        etudiant = row['etudiant']
        sans_comp = (
            all_ue_solos is not None
            and GrilleNotesGenerator._sans_compensation_defaillant(row, all_ecs, all_ue_solos)
        )
        for ec in all_ecs:
            note = row['notes_ec'].get(ec.id)
            if note is None:
                credits_ec[ec.id] = None
                continue
            note_dec = Decimal(str(note))
            if engine is not None:
                seuil = ec.seuil_validation or engine.parametres.seuil_validation
                if sans_comp:
                    credits_ec[ec.id] = (
                        int(ec.credits_ects) if engine._note_depasse_seuil(note_dec, seuil) else 0
                    )
                elif engine.valider_ec(etudiant, ec, note_dec):
                    credits_ec[ec.id] = int(ec.credits_ects)
                else:
                    credits_ec[ec.id] = 0
                continue
            if credits_ec.get(ec.id) is not None:
                continue
            seuil = Decimal(str(ec.seuil_validation or 10))
            credits_ec[ec.id] = int(ec.credits_ects) if note_dec >= seuil else 0

    @staticmethod
    def _calculer_credit_semestre_grille(row, all_ecs, all_ue_solos=None, engine=None):
        """
        Total crédits affiché en fin de ligne = somme des colonnes crédit EC visibles.
        Les cellules vides (note absente) ne participent pas au total.
        """
        total = 0
        for ec in all_ecs:
            credit = row.get('credits_ec', {}).get(ec.id)
            if credit is not None:
                total += int(credit)

        if all_ue_solos:
            etudiant = row['etudiant']
            for ue in all_ue_solos:
                note = row['notes_ue'].get(ue.id)
                if note is None:
                    continue
                note_dec = Decimal(str(note))
                if engine is not None:
                    if engine.valider_ue(etudiant, ue, note_dec):
                        total += int(ue.credits_ects)
                else:
                    seuil = Decimal(str(ue.seuil_validation or 10))
                    if note_dec >= seuil:
                        total += int(ue.credits_ects)
        return total

    @staticmethod
    def _fmt_entier_grille(value):
        """Affichage entier sans partie décimale (ex. 400, pas 400.00)."""
        if value is None:
            return None
        return str(int(Decimal(str(value)).quantize(Decimal('1'))))

    def _enrichir_notes_depuis_bdc(self, row, session, all_ecs, all_ue_solos):
        """Complète les notes manquantes depuis NoteEC / NoteUE en base."""
        if not session:
            return
        etudiant = row['etudiant']
        for ec in all_ecs:
            if row['notes_ec'].get(ec.id) is not None:
                continue
            note_ec = NoteEC.objects.filter(
                etudiant=etudiant, ec=ec, session=session,
            ).first()
            if note_ec and note_ec.note_finale is not None:
                row['notes_ec'][ec.id] = note_ec.note_finale
        for ue in all_ue_solos:
            if row['notes_ue'].get(ue.id) is not None:
                continue
            note_ue = NoteUE.objects.filter(
                etudiant=etudiant, ue=ue, session=session,
            ).first()
            if note_ue and note_ue.note_finale is not None:
                row['notes_ue'][ue.id] = note_ue.note_finale

    @staticmethod
    def _appliquer_decision_jury(row, decision_jury):
        """Reporte la décision officielle du jury sur la ligne étudiant."""
        if not decision_jury:
            return False
        row['decision'] = decision_jury.decision
        row['decision_label'] = decision_jury.get_decision_display()
        if decision_jury.moyenne_semestre is not None:
            row['moy_semestre'] = decision_jury.moyenne_semestre
        return True

    @staticmethod
    def _moyennes_par_categorie(resultat):
        """Moyennes pondérées par crédits ECTS des UE catégorie A et B."""
        moy_a_num = moy_a_den = moy_b_num = moy_b_den = Decimal('0.00')
        for data in resultat.get('notes_ue', {}).values():
            note = data.get('note')
            ue = data.get('ue')
            if note is None or ue is None:
                continue
            poids = ue.credits_ects or Decimal('0.00')
            if poids <= 0:
                continue
            if ue.categorie == 'B':
                moy_b_num += note * poids
                moy_b_den += poids
            else:
                moy_a_num += note * poids
                moy_a_den += poids

        moy_a = (moy_a_num / moy_a_den).quantize(Decimal('0.01')) if moy_a_den else None
        moy_b = (moy_b_num / moy_b_den).quantize(Decimal('0.01')) if moy_b_den else None
        return moy_a, moy_b

    def _structure_semestre_filiere(self):
        """UE / EC du semestre pour la filière (ordre grille)."""
        ues = UniteEnseignement.objects.filter(
            semestre=self.semestre,
            filiere=self.filiere,
            active=True,
        ).order_by('ordre', 'code')
        all_ecs = []
        all_ue_solos = []
        for ue in ues:
            ecs = list(ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code'))
            if not ecs:
                all_ue_solos.append(ue)
            else:
                all_ecs.extend(ecs)
        return ues, all_ecs, all_ue_solos

    def construire_ligne_etudiant(
        self,
        etudiant,
        all_ecs,
        all_ue_solos,
        *,
        session_grille=None,
        engine=None,
        decisions_jury=None,
    ):
        """Calcule notes, crédits capitalisés, synthèse et décision (aligné grille)."""
        from deliberations.services import DeliberationEngine

        if session_grille is None:
            session = self.session
            if session is None:
                session = self.semestre.sessions.filter(active=True).first()
            session_grille = self._session_effective_grille(session)
        if engine is None and session_grille:
            engine = DeliberationEngine(session_grille, self.promotion)
        if decisions_jury is None:
            decisions_jury = self._decisions_jury_par_etudiant()

        row = {
            'etudiant': etudiant,
            'notes_ec': {},
            'notes_ue': {},
            'credits_ec': {},
            'moy_a': None,
            'moy_b': None,
            'moy_semestre': None,
            'credit_semestre': 0,
            'note_ponderee': None,
            'decision': '',
            'decision_label': '',
        }
        if engine:
            resultat = engine.traiter_etudiant(etudiant)
            for ec in all_ecs:
                ec_data = resultat['notes_ec'].get(ec.id, {})
                row['notes_ec'][ec.id] = ec_data.get('note', None)
            for ue in all_ue_solos:
                ue_data = resultat['notes_ue'].get(ue.id, {})
                row['notes_ue'][ue.id] = ue_data.get('note', None)
            row['moy_a'], row['moy_b'] = self._moyennes_par_categorie(resultat)
            row['moy_semestre'] = resultat.get('moyenne_semestre', None)

            decision_jury = decisions_jury.get(etudiant.id)
            if not self._appliquer_decision_jury(row, decision_jury):
                decision_code = engine.produire_decision(etudiant, resultat)
                row['decision'] = decision_code
                row['decision_label'] = self._decision_label(decision_code)
        else:
            for ec in all_ecs:
                note_ec = NoteEC.objects.filter(
                    etudiant=etudiant, ec=ec, session=session_grille,
                ).first()
                row['notes_ec'][ec.id] = note_ec.note_finale if note_ec else None
                if note_ec and note_ec.valide and note_ec.note_finale is not None:
                    row['credits_ec'][ec.id] = int(note_ec.credits_obtenus or ec.credits_ects)
            for ue in all_ue_solos:
                note_ue = NoteUE.objects.filter(
                    etudiant=etudiant, ue=ue, session=session_grille,
                ).first()
                row['notes_ue'][ue.id] = note_ue.note_finale if note_ue else None
            decision_jury = decisions_jury.get(etudiant.id)
            self._appliquer_decision_jury(row, decision_jury)

        self._enrichir_notes_depuis_bdc(row, session_grille, all_ecs, all_ue_solos)
        self._remplir_credits_ec(row, all_ecs, engine, all_ue_solos)
        row['credit_semestre'] = self._calculer_credit_semestre_grille(
            row, all_ecs, all_ue_solos, engine,
        )
        row['note_ponderee'] = self._calculer_note_ponderee(
            all_ecs, all_ue_solos, row['notes_ec'], row['notes_ue'],
        )
        self._masquer_synthese_si_note_manquante(row, all_ecs, all_ue_solos)
        return row

    @staticmethod
    def _credit_capitalise_ue_solo(row, ue, engine, all_ecs, all_ue_solos):
        """Crédits capitalisés pour une UE sans EC (mêmes règles que la grille)."""
        note = row['notes_ue'].get(ue.id)
        if note is None:
            return None
        if engine is None:
            seuil = Decimal(str(ue.seuil_validation or 10))
            return int(ue.credits_ects) if Decimal(str(note)) >= seuil else 0
        etudiant = row['etudiant']
        note_dec = Decimal(str(note))
        seuil = ue.seuil_validation or engine.parametres.seuil_validation
        sans_comp = GrilleNotesGenerator._sans_compensation_defaillant(row, all_ecs, all_ue_solos)
        if sans_comp:
            return int(ue.credits_ects) if engine._note_depasse_seuil(note_dec, seuil) else 0
        if engine.valider_ue(etudiant, ue, note_dec):
            return int(ue.credits_ects)
        return 0

    @staticmethod
    def _fmt_credit_grille(credit):
        if credit is None:
            return '-'
        return str(int(credit))

    def _build_grid_data(self):
        from deliberations.services import DeliberationEngine

        session = self.session
        if session is None:
            session = self.semestre.sessions.filter(active=True).first()
        session_grille = self._session_effective_grille(session)
        ues, all_ecs, all_ue_solos = self._structure_semestre_filiere()

        column_specs = []
        ue_column_indices = []
        ec_pair_cols = []  # (col_cat, col_credit) pour chaque EC
        col_idx = 0

        for ue in ues:
            ecs = list(ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code'))

            column_specs.append({'type': 'ue', 'obj': ue, 'ecs': ecs})
            ue_column_indices.append(2 + col_idx)
            col_idx += 1

            if not ecs:
                continue

            for ec in ecs:
                start = col_idx
                column_specs.append({'type': 'ec_cat', 'obj': ec, 'ue_code': ue.code})
                column_specs.append({'type': 'ec_credit', 'obj': ec, 'ue_code': ue.code})
                ec_pair_cols.append((2 + start, 2 + start + 1))
                col_idx += 2

        inscriptions = Inscription.objects.filter(
            classe__promotion=self.promotion,
            annee_academique=self.annee_academique,
        ).eligibles_grille_notes(semestre=self.semestre, session=session_grille).select_related('etudiant', 'classe').order_by(
            'etudiant__nom', 'etudiant__prenom', 'etudiant__numero_etudiant',
        )

        engine = DeliberationEngine(session_grille, self.promotion) if session_grille else None
        decisions_jury = self._decisions_jury_par_etudiant()
        rows_data = []
        for idx_etud, inscription in enumerate(inscriptions, start=1):
            row = self.construire_ligne_etudiant(
                inscription.etudiant,
                all_ecs,
                all_ue_solos,
                session_grille=session_grille,
                engine=engine,
                decisions_jury=decisions_jury,
            )
            row['numero'] = idx_etud
            rows_data.append(row)

        return {
            'column_specs': column_specs,
            'ue_column_indices': ue_column_indices,
            'ec_pair_cols': ec_pair_cols,
            'all_ecs': all_ecs,
            'all_ue_solos': all_ue_solos,
            'rows': rows_data,
            'session': session_grille,
        }

    def _nom_column_width(self, rows_data, font_size=6):
        """Largeur minimale pour afficher chaque nom sur une seule ligne."""
        max_w = stringWidth('NOM - POSTNOM - PRENOM', 'Helvetica', font_size)
        for row in rows_data:
            etu = row['etudiant']
            label = etu.identite_cotation
            max_w = max(max_w, stringWidth(label, 'Helvetica', font_size))
        return max_w + 0.5 * cm

    def _compute_column_widths(self, column_specs, n_summary, col_nom_override=None, landscape_w=842):
        """Répartit les largeurs pour tenir dans la page paysage A4."""
        margin_h = 2.4 * cm
        usable = landscape_w - margin_h
        col_n = max(0.8 * cm, stringWidth('100', 'Helvetica', 6) + 0.35 * cm)
        col_nom = col_nom_override or (2.4 * cm)
        col_nom = min(max(col_nom, 2.2 * cm), usable * 0.28)

        col_credit = 0.32 * cm
        n_credit = sum(1 for spec in column_specs if spec['type'] == 'ec_credit')
        credit_total = n_credit * col_credit
        remaining = usable - col_n - col_nom - credit_total

        n_flex_specs = len(column_specs) - n_credit
        sum_share = min(0.28, n_summary * 0.045) if n_summary else 0
        ec_ue_share = 1.0 - sum_share
        per_spec = (remaining * ec_ue_share) / n_flex_specs if n_flex_specs else 0
        per_sum = (remaining * sum_share) / n_summary if n_summary else 0

        per_spec = max(per_spec, 0.20 * cm)
        per_sum = max(per_sum, 0.68 * cm)

        widths = [col_n, col_nom]
        for spec in column_specs:
            if spec['type'] == 'ec_credit':
                widths.append(col_credit)
            else:
                widths.append(per_spec)
        for _ in range(n_summary):
            widths.append(per_sum)

        total = sum(widths)
        if total > usable:
            scale = usable / total
            widths = [w * scale for w in widths]

        return widths

    def _header_font_size(self, col_width_pt, default=6):
        """Réduit la police des en-têtes verticaux si les colonnes sont étroites."""
        if col_width_pt < 0.32 * cm:
            return max(4, default - 2)
        if col_width_pt < 0.45 * cm:
            return max(5, default - 1)
        return default

    def _build_table(self, data):
        column_specs = data['column_specs']
        ue_column_indices = data['ue_column_indices']
        ec_pair_cols = data['ec_pair_cols']
        all_ecs = data['all_ecs']
        all_ue_solos = data['all_ue_solos']
        rows_data = data['rows']

        n_cols = len(column_specs)
        n_summary = 6
        n_header_rows = 3

        widths = self._compute_column_widths(
            column_specs,
            n_summary,
            col_nom_override=self._nom_column_width(rows_data, font_size=6),
        )
        ec_cat_widths = [
            w for w, spec in zip(widths[2:], column_specs) if spec['type'] == 'ec_cat'
        ]
        col_flex = min(ec_cat_widths) if ec_cat_widths else (widths[2] if len(widths) > 2 else 0.4 * cm)
        hdr_ec_fs = self._header_font_size(col_flex, default=6)
        hdr_ue_fs = self._header_font_size(col_flex, default=7)
        hdr_sum_fs = self._header_font_size(widths[-1] if widths else col_flex, default=6)

        start_sum = 2 + n_cols

        # ========== LIGNE 0 : en-têtes tournés ==========
        row0 = [Paragraph('<b>N°</b>', ParagraphStyle('gr_num_hdr', parent=self.st_header, alignment=TA_CENTER)), Paragraph("<b>UE</b>", ParagraphStyle('gr_ue', parent=self.st_header, alignment=TA_CENTER))]
        for spec in column_specs:
            nom = spec['obj'].nom or ''
            if len(nom) > 30:
                nom = nom[:27] + '...'
            txt = nom
            if spec['type'] == 'ue':
                row0.append(RotatedText(txt, font_size=hdr_ue_fs, bold=True, color=self.BLACK))
            elif spec['type'] == 'ec_cat':
                row0.append(RotatedText(txt, font_size=hdr_ec_fs, bold=False, color=self.BLACK))
            else:
                row0.append('')
        for txt in ["Note Pondérée", "Moy. cat. A", "Moy. cat. B",
                     "Moyenne Semestre", "Crédit Semestre", "Décision Semestre"]:
            row0.append(RotatedText(txt, font_size=hdr_sum_fs, bold=True, color=self.BLACK))

        # ========== LIGNE 1 : Catégorie & Crédit ==========
        row_cat = ['', Paragraph("<b>Catégorie &amp; Crédit</b>", self.st_header)]
        for spec in column_specs:
            if spec['type'] == 'ue':
                row_cat.append('')
            elif spec['type'] == 'ec_cat':
                cat = spec['obj'].ue.categorie if hasattr(spec['obj'], 'ue') and spec['obj'].ue_id else 'A'
                row_cat.append(cat)
            else:
                row_cat.append(f"{int(spec['obj'].credits_ects)}")
        total_credits_all = sum(int(ec.credits_ects) for ec in all_ecs)
        total_credits_all += sum(int(ue.credits_ects) for ue in all_ue_solos)
        for idx in range(n_summary):
            if idx == 4:  # Crédit Semestre
                row_cat.append(str(total_credits_all))
            else:
                row_cat.append('-')

        # ========== LIGNE 2 : MAXIMA ==========
        row_max = ['', Paragraph("<b>MAXIMA</b>", self.st_header)]
        for spec in column_specs:
            if spec['type'] == 'ec_credit':
                row_max.append('')
            else:
                row_max.append("20")
        total_credits_all = sum(int(ec.credits_ects) for ec in all_ecs)
        total_credits_all += sum(int(ue.credits_ects) for ue in all_ue_solos)
        max_np = 20 * total_credits_all
        for idx, v in enumerate([self._fmt_entier_grille(max_np) or '-', "20", "20", "20", "30", "-"]):
            if idx == 4:  # Crédit Semestre → vide
                row_max.append('')
            else:
                row_max.append(v)

        # ========== LIGNES ÉTUDIANTS ==========
        header_rows = [row0, row_cat, row_max]
        data_rows = list(header_rows)

        for r in rows_data:
            etu = r['etudiant']
            nom_label = etu.identite_cotation
            dr = [
                Paragraph(str(r['numero']), self.st_num),
                Paragraph(f'<nobr>{nom_label}</nobr>', self.st_nom),
            ]
            for spec in column_specs:
                if spec['type'] == 'ue':
                    ue = spec['obj']
                    if ue.id in {u.id for u in all_ue_solos}:
                        note = r['notes_ue'].get(ue.id)
                        dr.append(f"{note:.2f}" if note is not None else "-")
                    else:
                        dr.append('')
                elif spec['type'] == 'ec_cat':
                    note = r['notes_ec'].get(spec['obj'].id)
                    dr.append(f"{note:.2f}" if note is not None else "-")
                elif spec['type'] == 'ec_credit':
                    credit = r.get('credits_ec', {}).get(spec['obj'].id)
                    if credit is None:
                        dr.append("-")
                    else:
                        dr.append(str(int(credit)))
            # Note Pondérée = Σ(note × crédit)
            np_txt = self._fmt_entier_grille(r.get('note_ponderee'))
            dr.append(np_txt if np_txt else '-')
            dr.append(f"{r['moy_a']:.2f}" if r.get('moy_a') is not None else "-")
            dr.append(f"{r['moy_b']:.2f}" if r.get('moy_b') is not None else "-")
            dr.append(f"{r['moy_semestre']:.2f}" if r['moy_semestre'] is not None else "-")
            dr.append(str(r['credit_semestre']) if r.get('credit_semestre') is not None else "-")
            decision_txt = self._decision_grille_display(r)
            dr.append(decision_txt if decision_txt != '-' else '-')
            data_rows.append(dr)

        # ========== STYLES ==========
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), self.HEADER_BG),
            ('BACKGROUND', (0, 1), (-1, 1), self.CAT_BG),
            ('BACKGROUND', (0, 2), (-1, 2), self.MAX_BG),
            ('TEXTCOLOR', (0, 0), (-1, 2), self.BLACK),
            ('FONTNAME', (0, 0), (-1, 2), 'Helvetica-Bold'),
            ('LINEBELOW', (0, 2), (-1, 2), 0.6, colors.HexColor('#bdbdbd')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 3), (1, -1), 'LEFT'),
            ('VALIGN', (0, 1), (-1, 2), 'MIDDLE'),
            ('VALIGN', (0, 3), (-1, -1), 'MIDDLE'),
            ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
            ('VALIGN', (0, 0), (0, 2), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 5 if col_flex < 0.35 * cm else 6),
            ('TOPPADDING', (0, 0), (-1, 2), 1),
            ('BOTTOMPADDING', (0, 0), (-1, 2), 1),
            ('TOPPADDING', (0, 3), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 3), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ]

        decision_col = start_sum + n_summary - 1
        style.append(('ALIGN', (decision_col, 3), (decision_col, -1), 'CENTER'))
        for c_cat, c_cr in ec_pair_cols:
            style.append(('SPAN', (c_cat, 0), (c_cr, 0)))

        for i, spec in enumerate(column_specs):
            if spec['type'] == 'ec_credit':
                c = 2 + i
                style.append(('LEFTPADDING', (c, 0), (c, -1), 1))
                style.append(('RIGHTPADDING', (c, 0), (c, -1), 1))

        # Ligne 0 : en-têtes UE/EC tournés alignés en bas (non centré verticalement)
        for c in ue_column_indices:
            style.append(('VALIGN', (c, 0), (c, 0), 'BOTTOM'))
        for c_cat, _c_cr in ec_pair_cols:
            style.append(('VALIGN', (c_cat, 0), (c_cat, 0), 'BOTTOM'))
        for c in range(start_sum, start_sum + n_summary):
            style.append(('VALIGN', (c, 0), (c, 0), 'MIDDLE'))

        # Fond léger en-têtes UE (3 premières lignes seulement)
        for c in ue_column_indices:
            style.append(('BACKGROUND', (c, 0), (c, 2), self.UE_HDR_BG))

        # En-têtes résumé
        for c in range(start_sum, start_sum + n_summary):
            style.append(('BACKGROUND', (c, 0), (c, 2), self.SUM_HDR_BG))

        # Span N° sur 3 lignes, Nom NON spané (laisser "Catégorie & Crédit" visible)
        style.append(('SPAN', (0, 0), (0, 2)))
        style.append(('BACKGROUND', (0, 0), (1, 2), self.HEADER_BG))

        # Alternées (très légères)
        for i in range(3, len(data_rows), 2):
            style.append(('BACKGROUND', (0, i), (-1, i), self.ROW_ALT_BG))

        table = Table(data_rows, colWidths=widths, repeatRows=3)
        table.setStyle(TableStyle(style))
        return table, widths

    def _decision_label(self, decision):
        return {
            'admis': 'Admis',
            'admis_compensation': 'Admis par compensation',
            'admis_avec_dettes': 'Avec dettes',
            'defaillant': 'Défaillant',
            'redouble': 'Redouble',
            'exclu': 'Exclu',
            'ajourne': 'Ajourné',
            'report': 'Report',
        }.get(decision, decision or '-')

    def _decision_grille_display(self, row):
        """Sigle court pour la colonne Décision Semestre du PDF."""
        code = (row.get('decision') or '').strip()
        if not code:
            return '-'
        return _DECISION_SIGLES.get(code, code.upper())


def enregistrer_grille_notes_pdf(
    semestre,
    filiere,
    promotion,
    annee_academique,
    session,
    *,
    deliberation=None,
    genere_par=None,
    buffer=None,
):
    """Génère la grille de notes PDF et l'enregistre dans DocumentGenere."""
    from django.core.files.base import ContentFile
    from documents.models import DocumentGenere, TypeDocumentGenere

    buf = buffer or BytesIO()
    generator = GrilleNotesGenerator(
        semestre, filiere, promotion, annee_academique,
        session=session, deliberation=deliberation, buffer=buf,
    )
    generator.generate()
    pdf_bytes = buf.getvalue()

    filename = (
        f'grille_notes_{semestre.code}_{promotion.code}_{session.code}_{annee_academique.code}.pdf'
    )
    type_doc, _ = TypeDocumentGenere.objects.get_or_create(
        code='GRILLE_NOTES',
        defaults={'nom': 'Grille de notes', 'active': True},
    )

    if deliberation:
        lookup = {'type_document': type_doc, 'deliberation': deliberation}
        defaults = {
            'session': session,
            'fichier': ContentFile(pdf_bytes, name=filename),
            'genere_par': genere_par,
            'notes': f'promotion:{promotion.pk}',
        }
    else:
        lookup = {
            'type_document': type_doc,
            'session': session,
            'deliberation': None,
            'notes': f'promotion:{promotion.pk}',
        }
        defaults = {
            'fichier': ContentFile(pdf_bytes, name=filename),
            'genere_par': genere_par,
        }

    doc, _ = DocumentGenere.objects.update_or_create(**lookup, defaults=defaults)
    return doc, pdf_bytes
