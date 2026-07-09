"""
Services de génération de documents PDF avec ReportLab
"""
import os
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
    """Générateur de relevés de notes — format compact une page."""

    MARGIN_LR = 1.0 * cm
    MARGIN_TB = 0.8 * cm
    PAGE_HEIGHT = A4[1]
    ROW_LINE_EXTRA = 6.5
    ROW_LINE_MAX_EXTRA = 10

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
        self.title_font = min(12, self.body_font + 3)

    def _body_font_size(self):
        if self.ec_count <= 14:
            return 8
        if self.ec_count <= 20:
            return 7.5
        if self.ec_count <= 28:
            return 7
        return 6.5

    def _col_widths(self, ratios):
        total = sum(ratios)
        return [self.content_width * ratio / total for ratio in ratios]

    def generate(self):
        from reportlab.pdfgen import canvas as pdf_canvas

        c = pdf_canvas.Canvas(self.buffer, pagesize=A4)
        width, _height = A4
        x = self.MARGIN_LR
        y = self.PAGE_HEIGHT - self.MARGIN_TB

        y = self._draw_canvas_header(c, width, y)
        y -= 0.08 * cm
        y = self._draw_canvas_student(c, x, y)
        y -= 0.08 * cm
        y = self._draw_canvas_notes_table(c, x, y, self._collect_notes_data())
        y -= 0.08 * cm
        self._draw_canvas_signatures(c, width, y)

        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#64748b'))
        c.drawCentredString(width / 2, 0.75 * cm, 'Page 1')

        c.showPage()
        c.save()
        return self.buffer

    def _draw_canvas_header(self, c, width, y):
        lines = [
            ("ECOLE INFORMATIQUE DES FINANCES", self.body_font, True),
            (
                f"RELEVÉ DE NOTES — {self.semestre.code} — "
                f"{self.promotion.code} — {self.annee_academique.code}",
                self.title_font,
                True,
            ),
        ]
        for text, size, bold in lines:
            c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
            c.drawCentredString(width / 2, y, text)
            y -= size + 2
        return y

    def _draw_canvas_student(self, c, x, y):
        ins = self.inscription
        section = ins.section.nom if ins and ins.section else '—'
        lines = [
            (
                f"N° {self.etudiant.numero_etudiant}  |  "
                f"Nom {self.etudiant.nom}  |  "
                f"Prénom {self.etudiant.prenom}  |  "
                f"Naissance {self.etudiant.date_naissance.strftime('%d/%m/%Y')}"
            ),
            (
                f"Section {section}  |  "
                f"Filière {self.filiere.nom}  |  "
                f"Promotion {self.promotion.code}  |  "
                f"Semestre {self.semestre.code}"
            ),
        ]
        box_h = 2 * (self.body_font + 3) + 4
        c.setStrokeColor(colors.grey)
        c.setLineWidth(0.4)
        c.rect(x, y - box_h, self.content_width, box_h, stroke=1, fill=0)
        c.setFont('Helvetica', self.body_font)
        c.drawString(x + 4, y - self.body_font - 3, lines[0][:140])
        c.drawString(x + 4, y - self.body_font - 7 - self.body_font, lines[1][:140])
        return y - box_h

    def _truncate_cell(self, text, col_width):
        value = str(text or '')
        max_chars = max(4, int(col_width / (self.body_font * 0.42)))
        if len(value) > max_chars:
            return value[: max_chars - 1] + '…'
        return value

    def _notes_row_height_bounds(self):
        return (
            self.body_font + self.ROW_LINE_EXTRA,
            self.body_font + self.ROW_LINE_MAX_EXTRA,
        )

    def _draw_canvas_notes_table(self, c, x, y, data):
        col_widths = self._col_widths([1.1, 3.8, 0.8, 0.9, 0.8, 1.1])
        total_w = sum(col_widths)
        n_rows = len(data)
        bottom_limit = self.MARGIN_TB + 32
        min_row_h, max_row_h = self._notes_row_height_bounds()
        available = y - bottom_limit
        ideal_row_h = available / max(1, n_rows)
        if ideal_row_h < min_row_h:
            row_h = ideal_row_h
        else:
            row_h = min(max_row_h, max(min_row_h, ideal_row_h))
        table_bottom = y - row_h * n_rows

        for i, row in enumerate(data):
            top = y - i * row_h
            bottom = top - row_h
            if i == 0:
                c.setFillColor(colors.HexColor('#1a237e'))
                c.rect(x, bottom, total_w, row_h, stroke=0, fill=1)
                text_color = colors.white
                font = 'Helvetica-Bold'
            elif i >= n_rows - 3:
                c.setFillColor(colors.HexColor('#e8eaf6'))
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

            c.setStrokeColor(colors.grey)
            c.setLineWidth(0.35)
            c.rect(x, bottom, total_w, row_h, stroke=1, fill=0)

            x_cell = x
            if i >= n_rows - 2:
                c.setFillColor(text_color)
                c.setFont(font, self.body_font)
                label = self._truncate_cell(row[0], col_widths[0])
                c.drawString(x + 2, bottom + (row_h - self.body_font) / 2, label)
                span_text = self._truncate_cell(row[1], sum(col_widths[1:]))
                c.drawString(x + col_widths[0] + 2, bottom + (row_h - self.body_font) / 2, span_text)
                continue

            for j, cell in enumerate(row):
                c.setFillColor(text_color)
                c.setFont(font, self.body_font)
                text = self._truncate_cell(cell, col_widths[j])
                align_x = x_cell + 2
                if j >= 2:
                    align_x = x_cell + (col_widths[j] - c.stringWidth(text, font, self.body_font)) / 2
                c.drawString(align_x, bottom + (row_h - self.body_font) / 2, text)
                x_cell += col_widths[j]
                c.line(x_cell, bottom, x_cell, top)
        return table_bottom

    def _draw_canvas_signatures(self, c, width, y):
        c.setFont('Helvetica', self.body_font)
        c.drawCentredString(
            width / 2,
            y,
            f"Fait à Kinshasa, le {datetime.now().strftime('%d/%m/%Y')}",
        )
        y -= self.body_font + 8
        labels = ['Secrétaire du Jury', 'Membres du Jury', 'Président du Jury']
        col_w = self.content_width / 3
        x0 = self.MARGIN_LR
        for idx, label in enumerate(labels):
            cx = x0 + col_w * idx + col_w / 2
            c.drawCentredString(cx, y, label)
            c.line(cx - 45, y - 12, cx + 45, y - 12)

    def _collect_notes_data(self):
        engine = DeliberationEngine(self.session, self.promotion) if self.session else None
        resultat = engine.traiter_etudiant(self.etudiant) if engine else {}

        ues = UniteEnseignement.objects.filter(semestre=self.semestre, active=True).order_by('ordre', 'code')
        header = ['Code UE', 'Libellé', 'Cat.', 'CC', 'Cr.', 'Note pond.']
        data = [header]

        total_credits = 0
        total_np = 0.0
        cat_sum = {'A': 0.0, 'B': 0.0}
        cat_count = {'A': 0, 'B': 0}
        for ue in ues:
            ecs = ElementConstitutif.objects.filter(ue=ue, active=True).order_by('ordre', 'code')
            cat = ue.categorie or 'A'
            for ec_index, ec in enumerate(ecs):
                ec_data = resultat.get('notes_ec', {}).get(ec.id, {})
                note = ec_data.get('note', None)
                cr = int(ec.credits_ects)
                total_credits += cr
                np = float(note) * cr if note is not None else 0
                total_np += np
                if note is not None:
                    cat_sum[cat] += float(note)
                    cat_count[cat] += 1
                ue_code = ue.code if ec_index == 0 else ''
                libelle = f'{ec.code} — {ec.nom}'
                data.append([
                    ue_code,
                    libelle,
                    cat,
                    f'{note:.2f}' if note is not None else '-',
                    str(cr),
                    f'{np:.2f}',
                ])

        s = resultat.get('moyenne_semestre', None)
        co = int(resultat.get('credits_obtenus', 0) or 0)
        dec = engine.produire_decision(self.etudiant, resultat) if engine else ''
        mention = self._compute_mention(s)
        moy_a = cat_sum['A'] / cat_count['A'] if cat_count['A'] else 0
        moy_b = cat_sum['B'] / cat_count['B'] if cat_count['B'] else 0

        data.append(['Total', '', '', '', str(total_credits), f'{total_np:.2f}'])
        data.append([
            'Synthèse',
            (
                f"Moy.A {moy_a:.2f} · Moy.B {moy_b:.2f} · Moy. {s:.2f}"
                if s else f"Moy.A {moy_a:.2f} · Moy.B {moy_b:.2f}"
            ),
            '', '', '', '',
        ])
        data.append([
            'Résultat',
            f"Crédits capitalisés : {co} · {self._decision_label(dec)} · Mention : {mention}",
            '', '', '', '',
        ])
        return data

    def _decision_label(self, decision):
        return {'admis': 'Admis', 'admis_compensation': 'Admis par compensation',
                'admis_avec_dettes': 'Admis avec dettes', 'defaillant': 'Défaillant',
                'redouble': 'Redouble', 'exclu': 'Exclu',
                'ajourne': 'Ajourné', 'report': 'Report'}.get(decision, decision or '-')

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

    def _pv_bullet(self, text: str) -> Paragraph:
        return Paragraph(text, self.styles['PVBullet'], bulletText='•')

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
        story.extend(self._build_jury())
        story.extend(self._build_examen())
        story.extend(self._build_decisions())
        story.extend(self._build_souverainete())
        story.extend(self._build_cloture())
        story.extend(self._build_signatures())
        doc.build(story, onFirstPage=_draw_page_number_footer, onLaterPages=_draw_page_number_footer)
        return self.buffer

    def _build_header(self):
        elements = []
        logo = _pv_logo_flowable(_pv_find_logo_path())
        if logo:
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(INSTITUTION_NOM.upper(), self.styles['PVInstitution']))
        elements.append(Paragraph(
            f'{INSTITUTION_SIGLE} — Système Licence-Master-Doctorat (LMD)',
            self.styles['PVInstitutionSub'],
        ))
        elements.append(Paragraph(
            'PROCÈS-VERBAL DE DÉLIBÉRATION DU JURY LMD',
            self.styles['PVDocTitle'],
        ))
        return elements

    def _build_ouverture(self):
        date_val = self.deliberation.date_deliberation
        annee_lettres = _annee_en_lettres_fr(date_val.year)
        jour_lettres = _jour_en_lettres_fr(date_val.day)
        mois = _MOIS_FR[date_val.month - 1]
        date_seance = f'le {jour_lettres} {mois}'
        lieu = _PV_LIEU_DEFAUT
        semestre = _semestre_pv_libelle(self.deliberation, self.semestre)
        filiere = getattr(getattr(self.promotion, 'filiere', None), 'nom', '—')
        niveau = _niveau_pedagogique(self.promotion)
        texte = (
            f'L’an {annee_lettres}, {date_seance}, s’est tenu à <b>{lieu}</b>, '
            f'la réunion du jury de délibération du semestre <b>{semestre}</b> '
            f'de la filière <b>{filiere}</b>, niveau <b>{niveau}</b>, '
            f'conformément aux dispositions réglementaires du système '
            f'Licence-Master-Doctorat (LMD).'
        )
        return [self._pv_body(texte)]

    def _build_jury(self):
        elements = []
        comp = self.deliberation.composition_bureau
        president_nom = comp.get('president') or 'non désigné'
        secretaire = comp.get('secretaire') or ''
        elements.append(self._pv_body(
            f'Le jury de délibération du <b>{comp.get("promotion_label", "")}</b> '
            f'(année académique <b>{comp.get("annee_label", "")}</b>), '
            f'régulièrement constitué, était présidé par <b>{president_nom}</b>'
            + (f', avec <b>{secretaire}</b> en qualité de secrétaire' if secretaire else '')
            + ', en présence des membres suivants :'
        ))
        membres = comp.get('membres') or []
        if membres:
            for nom in membres:
                elements.append(self._pv_bullet(f'<b>{nom}</b>'))
        else:
            elements.append(self._pv_bullet('<i>Aucun autre membre convoqué.</i>'))
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_examen(self):
        annee = _annee_academique_libelle(self.deliberation, self.session)
        texte = (
            f'Après examen des résultats académiques des étudiants inscrits au titre '
            f'de l’année académique <b>{annee}</b>, le jury a procédé à l’analyse des '
            f'moyennes semestrielles, des notes par unités d’enseignement (UE), ainsi '
            f'que des cas particuliers conformément aux textes en vigueur.'
        )
        elements = [self._pv_body(texte)]
        if self.deliberation.notes:
            elements.append(self._pv_body(
                f'<i>Observations du jury :</i> {self.deliberation.notes}'
            ))
        return elements

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
        total = sum(stats.values())
        elements = [self._pv_body(
            'À l’issue des délibérations, les décisions suivantes ont été arrêtées :'
        )]
        if total:
            elements.append(self._pv_body(
                f'Sur <b>{total}</b> candidat(s) examiné(s), la répartition par décision '
                f'est la suivante :'
            ))
        definitions = [
            (
                'admis',
                'Admis',
                'Étudiants ayant obtenu une moyenne générale supérieure ou égale à 10/20 '
                'et validé l’ensemble des unités d’enseignement.',
            ),
            (
                'admis_compensation',
                'Admis par compensation',
                'Étudiants ayant obtenu une moyenne générale supérieure ou égale à 10/20, '
                'avec compensation entre unités d’enseignement.',
            ),
            (
                'ajourne',
                'Ajourné',
                'Étudiants n’ayant pas atteint la moyenne requise et ne remplissant pas '
                'les conditions de compensation.',
            ),
            (
                'defaillant',
                'Défaillant',
                'Étudiants absents aux évaluations ou n’ayant pas satisfait aux exigences '
                'minimales de participation.',
            ),
            (
                'admis_avec_dettes',
                'Admis avec dettes',
                'Étudiants autorisés à poursuivre avec des unités d’enseignement non validées '
                'à régulariser ultérieurement (le cas échéant).',
            ),
        ]
        for code, titre, description in definitions:
            effectif = _effectif_etudiants_fr(stats.get(code, 0))
            elements.append(self._pv_bullet(
                f'<b>{titre}</b> — <b>{effectif}</b> : {description}'
            ))
        autres = {
            k: v for k, v in stats.items()
            if k not in {d[0] for d in definitions} and v > 0
        }
        if autres:
            labels = dict(DecisionJury._meta.get_field('decision').choices)
            for code, nombre in sorted(autres.items()):
                libelle = labels.get(code, code)
                effectif = _effectif_etudiants_fr(nombre)
                elements.append(self._pv_bullet(
                    f'<b>{libelle}</b> — <b>{effectif}</b>.'
                ))
        if not total:
            elements.append(self._pv_body(
                '<i>Aucune décision individuelle n’a encore été enregistrée pour cette séance.</i>'
            ))
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_souverainete(self):
        return [self._pv_body(
            'Le jury a statué en toute souveraineté, dans le respect des principes '
            'd’équité, d’objectivité et de transparence.'
        )]

    def _build_cloture(self):
        aujourd_hui = date.today()
        jour = aujourd_hui.day
        mois = _MOIS_FR[aujourd_hui.month - 1]
        annee = aujourd_hui.year
        elements = [
            Paragraph(
                'En foi de quoi, le présent procès-verbal a été dressé pour servir '
                'et valoir ce que de droit.',
                self.styles['PVClosing'],
            ),
            Paragraph(
                f'Fait à {_PV_LIEU_DEFAUT}, le {jour} {mois} {annee}.',
                self.styles['PVClosing'],
            ),
        ]
        return elements

    def _build_signatures(self):
        comp = self.deliberation.composition_bureau
        elements = [Spacer(1, 0.6 * cm)]
        elements.append(Paragraph('Le Président du Jury', self.styles['PVSignatureTitle']))
        elements.append(Spacer(1, 1.2 * cm))
        elements.append(Paragraph('_________________________', self.styles['PVSignature']))
        president_nom = comp.get('president')
        if president_nom:
            elements.append(Paragraph(f'<b>{president_nom}</b>', self.styles['PVSignature']))

        secretaire = comp.get('secretaire')
        if secretaire:
            elements.append(Spacer(1, 0.8 * cm))
            elements.append(Paragraph('Le Secrétaire du Jury', self.styles['PVSignatureTitle']))
            elements.append(Spacer(1, 1.2 * cm))
            elements.append(Paragraph('_________________________', self.styles['PVSignature']))
            elements.append(Paragraph(f'<b>{secretaire}</b>', self.styles['PVSignature']))

        elements.append(Spacer(1, 0.8 * cm))
        elements.append(Paragraph('Les Membres du Jury', self.styles['PVSignatureTitle']))
        membres = comp.get('membres') or []
        if membres:
            for nom in membres:
                elements.append(Spacer(1, 0.9 * cm))
                elements.append(Paragraph('_________________________', self.styles['PVSignature']))
                elements.append(Paragraph(f'<b>{nom}</b>', self.styles['PVSignature']))
        else:
            elements.append(Spacer(1, 1.2 * cm))
            elements.append(Paragraph('_________________________', self.styles['PVSignature']))
        return elements


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

        doc.build(story, onFirstPage=_draw_page_number_footer, onLaterPages=_draw_page_number_footer)
        return buffer

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
        Affichée dès qu'au moins une note est disponible.
        """
        total = Decimal('0.00')
        has_note = False
        for ec in all_ecs:
            note = notes_ec.get(ec.id)
            if note is None:
                continue
            has_note = True
            total += Decimal(str(note)) * Decimal(str(ec.credits_ects or 0))
        for ue in all_ue_solos:
            note = notes_ue.get(ue.id)
            if note is None:
                continue
            has_note = True
            total += Decimal(str(note)) * Decimal(str(ue.credits_ects or 0))
        return int(total.quantize(Decimal('1'))) if has_note else None

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
        if decision_jury.credits_obtenus is not None:
            row['credit_semestre'] = int(decision_jury.credits_obtenus)
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

    def _build_grid_data(self):
        from deliberations.services import DeliberationEngine

        session = self.session
        if session is None:
            session = self.semestre.sessions.filter(active=True).first()
        session_grille = self._session_effective_grille(session)
        ues = UniteEnseignement.objects.filter(
            semestre=self.semestre,
            filiere=self.filiere,
            active=True,
        ).order_by('ordre', 'code')

        all_ecs = []
        all_ue_solos = []
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
                all_ue_solos.append(ue)
                continue

            for ec in ecs:
                start = col_idx
                column_specs.append({'type': 'ec_cat', 'obj': ec, 'ue_code': ue.code})
                column_specs.append({'type': 'ec_credit', 'obj': ec, 'ue_code': ue.code})
                ec_pair_cols.append((2 + start, 2 + start + 1))
                all_ecs.append(ec)
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
            etudiant = inscription.etudiant
            row = {
                'numero': idx_etud,
                'etudiant': etudiant,
                'notes_ec': {},
                'notes_ue': {},
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
                row['credit_semestre'] = (
                    int(resultat.get('credits_obtenus', 0)) if resultat.get('credits_obtenus') else 0
                )

                decision_jury = decisions_jury.get(etudiant.id)
                if not self._appliquer_decision_jury(row, decision_jury):
                    decision_code = engine.produire_decision(etudiant, resultat)
                    row['decision'] = decision_code
                    row['decision_label'] = self._decision_label(decision_code)
            else:
                for ec in all_ecs:
                    note_ec = NoteEC.objects.filter(etudiant=etudiant, ec=ec, session=session_grille).first()
                    row['notes_ec'][ec.id] = note_ec.note_finale if note_ec else None
                for ue in all_ue_solos:
                    note_ue = NoteUE.objects.filter(etudiant=etudiant, ue=ue, session=session_grille).first()
                    row['notes_ue'][ue.id] = note_ue.note_finale if note_ue else None
                decision_jury = decisions_jury.get(etudiant.id)
                self._appliquer_decision_jury(row, decision_jury)
            self._enrichir_notes_depuis_bdc(row, session_grille, all_ecs, all_ue_solos)
            row['note_ponderee'] = self._calculer_note_ponderee(
                all_ecs, all_ue_solos, row['notes_ec'], row['notes_ue'],
            )
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
                    note = r['notes_ec'].get(spec['obj'].id)
                    seuil = float(spec['obj'].seuil_validation or 10)
                    if note is None:
                        dr.append("-")
                    elif note >= seuil:
                        dr.append(str(int(spec['obj'].credits_ects)))
                    else:
                        dr.append("0")
            # Note Pondérée = Σ(note × crédit)
            np_txt = self._fmt_entier_grille(r.get('note_ponderee'))
            dr.append(Paragraph(np_txt, self.st_num) if np_txt else '-')
            dr.append(f"{r['moy_a']:.2f}" if r.get('moy_a') is not None else "-")
            dr.append(f"{r['moy_b']:.2f}" if r.get('moy_b') is not None else "-")
            dr.append(f"{r['moy_semestre']:.2f}" if r['moy_semestre'] is not None else "-")
            dr.append(str(r['credit_semestre']))
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
        return {
            'admis': 'ADM',
            'admis_compensation': 'COMP',
            'defaillant': 'DEF',
            'ajourne': 'AJ',
            'admis_avec_dettes': 'ADM-D',
            'redouble': 'RED',
            'exclu': 'EXC',
            'report': 'REP',
        }.get(code, code.upper())


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
