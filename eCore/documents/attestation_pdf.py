"""
Génération PDF des attestations — en-tête institutionnel + corps de texte.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse
from reportlab.lib.utils import ImageReader

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph

from documents.attestation_border import draw_certificate_border
from documents.attestation_watermark import draw_pale_background_motif
from documents import attestation_fond as att_fond
from documents.attestation_fond import (
    AttestationFondVectoriel,
    BLUE,
    FONT_PIED,
    draw_fond_frequentation,
    ensure_arial_fonts,
)

INK = BLUE

MARGIN_LR = 2.05 * cm
MARGIN_TOP_ENTETE = 2.55 * cm
MARGIN_TOP = MARGIN_TOP_ENTETE
GAP_AVANT_TITRE_ATTESTATION = 1.1 * cm
GAP_TITRE_SOULIGNEMENT = 0.55 * cm
GAP_APRES_TITRE_ATTESTATION = 1.15 * cm
Y_PIED_PAGE = 2.35 * cm
PIED_MENTION_FONT_SIZE = 11
PIED_NUMERO_FONT_SIZE = 10
QRCODE_SIZE = 2.0 * cm
QRCODE_GAP_FOOTER = 0.35 * cm
SIGNATURE_FONT_SIZE = 13
SIGNATURE_NOM_FONT_SIZE = 14
SIGNATURE_FONCTION_FONT_SIZE = 13
SIGNATURE_LINE_H = 22
SIGNATURE_GAP_BEFORE_NOM = 15
GAP_CORPS_SIGNATURE = 0.45 * cm
SIGNATURE_BLOCK_HEIGHT = (
    3 * SIGNATURE_LINE_H + SIGNATURE_GAP_BEFORE_NOM + SIGNATURE_FONCTION_FONT_SIZE + 8
)
Y_SIGNATURE_MIN = Y_PIED_PAGE + SIGNATURE_BLOCK_HEIGHT
Y_CORPS_BOTTOM_MAX = Y_SIGNATURE_MIN + GAP_CORPS_SIGNATURE
CLOTURE_ATTESTATION = (
    'La présente attestation lui est délivrée pour faire valoir ce que de droit.'
)
BODY_FONT_SIZE = 13
BODY_LEADING = 24
GAP_LIGNE_BLANCHE_AVANT_CLOTURE = 19
FIRST_LINE_INDENT = 3 * cm

SIGNATAIRE_NOM = 'Anselme MUFWENGE KAPAY'
SIGNATAIRE_TITRE = 'Secrétaire Général Académique'
SIGNATAIRE_FONCTION = 'Chef de Division Formation'
INSTITUTION_NOM = "l'École Informatique des Finances"
INSTITUTION_SIGLE = 'E.I.FI'


def _student_parts(etudiant) -> tuple[str, str, str]:
    nom_raw = (etudiant.nom or '').strip()
    prenom = (etudiant.prenom or '').strip()
    if prenom == '—':
        prenom = ''
    tokens = nom_raw.split(None, 1)
    nom = (tokens[0] if tokens else '').upper()
    postnom = (tokens[1] if len(tokens) > 1 else '').upper()
    prenom_fmt = prenom[0].upper() + prenom[1:].lower() if len(prenom) > 1 else prenom.upper()
    return nom, postnom, prenom_fmt


def _student_display_name(etudiant) -> str:
    nom, postnom, prenom = _student_parts(etudiant)
    parts = [p for p in (nom, postnom, prenom) if p]
    return ' '.join(parts) or '—'


def _numero_afe(attestation) -> str:
    year = attestation.date_delivrance.year if attestation else datetime.now().year
    seq = attestation.pk if attestation and attestation.pk else 0
    return f'{seq:04d}/{year}'


def _nom_etudiant_fichier(etudiant) -> str:
    nom = _student_display_name(etudiant).strip()
    nom = re.sub(r'\s+', '_', nom)
    nom = re.sub(r'[^\w\-]', '', nom, flags=re.UNICODE)
    return nom or 'ETUDIANT'


def build_attestation_filename(attestation) -> str:
    """Nom du PDF : ATTESTATION-FREQ-NOM_ETUDIANT-NUMERO_AFE pour la fréquentation."""
    etudiant = attestation.inscription.etudiant
    if attestation.type_attestation.code == 'frequentation':
        afe = _numero_afe(attestation).replace('/', '-')
        return f'ATTESTATION-FREQ-{_nom_etudiant_fichier(etudiant)}-{afe}.pdf'
    return f'attestation_{attestation.numero}_{etudiant.numero_etudiant}.pdf'


def _public_base_url() -> str:
    configured = getattr(settings, 'CARD_PUBLIC_BASE_URL', None) or 'http://127.0.0.1:8000/'
    return configured.rstrip('/') + '/'


def _attestation_qr_payload(attestation) -> str:
    if attestation and attestation.pk:
        path = reverse('documents:attestation_pdf', kwargs={'pk': attestation.pk})
        return urljoin(_public_base_url(), path.lstrip('/'))
    return urljoin(_public_base_url(), 'documents/attestations/')


def _draw_qrcode(c: pdf_canvas.Canvas, x: float, y_bottom: float, payload: str, size: float):
    if not payload:
        return
    import qrcode

    c.saveState()
    try:
        qr = qrcode.QRCode(border=1, box_size=8)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        c.drawImage(ImageReader(buf), x, y_bottom, width=size, height=size, mask='auto')
    finally:
        c.restoreState()


def _niveau_label(inscription) -> str:
    promotion = inscription.promotion
    if not promotion:
        return '—'
    raw = (promotion.nom or promotion.code or '').strip()
    if not raw:
        return '—'
    nom_upper = raw.upper()
    if nom_upper.startswith('PREMIER MASTER') or nom_upper.startswith('PREMIERE MASTER'):
        return 'PREMIERE ANNEE MASTER LMD'
    return raw


def _annee_academique(ins) -> str:
    annee = ins.annee_academique
    if not annee:
        return '—'
    if annee.annee_debut and annee.annee_fin:
        return f'{annee.annee_debut}-{annee.annee_fin}'
    return annee.code



class AttestationGenerator:
    """Génère l'attestation PDF (en-tête + corps + signature)."""

    TITRES_PAR_TYPE = {
        'frequentation': 'ATTESTATION De FREQUENTATION',
        'inscription': "ATTESTATION D'INSCRIPTION",
        'reussite': 'ATTESTATION DE RÉUSSITE',
        'stage': 'ATTESTATION DE STAGE',
    }

    def __init__(self, attestation=None, etudiant=None, inscription=None, type_attestation='frequentation', buffer=None):
        self.buffer = buffer if buffer else BytesIO()
        if attestation is not None:
            self.attestation = attestation
            self.etudiant = attestation.inscription.etudiant
            self.inscription = attestation.inscription
            self.type_attestation = attestation.type_attestation.code
            self.type_nom = attestation.type_attestation.nom
            self.date_delivrance = attestation.date_delivrance
            self.lieu_delivrance = attestation.lieu_delivrance or 'Kinshasa'
            self.objet = (attestation.objet or '').strip()
        else:
            self.attestation = None
            self.etudiant = etudiant
            self.inscription = inscription
            self.type_attestation = type_attestation
            self.type_nom = 'Attestation de fréquentation'
            self.date_delivrance = datetime.now().date()
            self.lieu_delivrance = 'Kinshasa'
            self.objet = ''

    def _document_title(self) -> str:
        return self.TITRES_PAR_TYPE.get(
            self.type_attestation,
            (self.type_nom or 'Attestation').upper(),
        )

    def generate(self):
        ensure_arial_fonts()
        width, height = A4
        c = pdf_canvas.Canvas(self.buffer, pagesize=A4)

        has_fond_image = False
        if self.type_attestation == 'frequentation':
            has_fond_image = draw_fond_frequentation(c, width, height)

        if not has_fond_image:
            draw_certificate_border(
                c,
                width,
                height,
                margin_out=AttestationFondVectoriel.M_OUT,
                margin_in=AttestationFondVectoriel.M_IN,
            )
            draw_pale_background_motif(
                c,
                width,
                height,
                margin_out=AttestationFondVectoriel.M_OUT,
                margin_in=AttestationFondVectoriel.M_IN,
            )

        content_w = width - 2 * MARGIN_LR
        y_corps_top = AttestationFondVectoriel().draw_entete(
            c,
            width,
            height,
            titre=self._document_title(),
            margin_top=MARGIN_TOP_ENTETE,
            margin_h=MARGIN_LR + 1.2 * cm,
            gap_avant_titre=GAP_AVANT_TITRE_ATTESTATION,
            gap_titre_soulignement=GAP_TITRE_SOULIGNEMENT,
            gap_apres_titre=GAP_APRES_TITRE_ATTESTATION,
        )
        y_body_end = self._draw_body(c, MARGIN_LR, content_w, y_corps_top, Y_CORPS_BOTTOM_MAX)
        y_signature_top = max(y_body_end - GAP_CORPS_SIGNATURE, Y_SIGNATURE_MIN)
        self._draw_signature(c, width, y_signature_top)
        self._draw_numero(c, width)
        c.showPage()
        c.save()
        return self.buffer

    def _body_style(self):
        return ParagraphStyle(
            'AttestationBody',
            fontName=att_fond.FONT_CORPS,
            fontSize=BODY_FONT_SIZE,
            leading=BODY_LEADING,
            alignment=TA_JUSTIFY,
            textColor=INK,
            firstLineIndent=FIRST_LINE_INDENT,
        )

    def _cloture_style(self):
        return ParagraphStyle(
            'AttestationCloture',
            parent=self._body_style(),
            firstLineIndent=FIRST_LINE_INDENT,
        )

    def _build_body_parts(self) -> tuple[str, str | None]:
        if self.objet:
            return self.objet.replace('\n', '<br/>'), None

        etu = self.etudiant
        ins = self.inscription
        nom_aff = _student_display_name(etu)
        date_naiss = etu.date_naissance.strftime('%d/%m/%Y')
        lieu_naiss = etu.lieu_naissance or 'Kinshasa'
        annee = _annee_academique(ins)
        section = ins.section.nom if ins.section else '—'
        option = ins.filiere.nom if ins.filiere else '—'
        niveau = _niveau_label(ins)
        signataire = (
            f'<b>{SIGNATAIRE_NOM}</b>, {SIGNATAIRE_TITRE} et {SIGNATAIRE_FONCTION} '
            f'de {INSTITUTION_NOM} ({INSTITUTION_SIGLE})'
        )

        if self.type_attestation == 'inscription':
            corps = (
                f'Je soussigné, {signataire}, atteste par la présente que le (la) nommé(e) '
                f'<b>{nom_aff}</b>, né(e) à {lieu_naiss}, le {date_naiss}, '
                f'est inscrit(e) sous le n° <b>{ins.numero_inscription}</b> '
                f"pour l'année académique <b>{annee}</b>."
            )
        elif self.type_attestation == 'reussite':
            corps = (
                f'Je soussigné, {signataire}, atteste par la présente que le (la) nommé(e) '
                f'<b>{nom_aff}</b>, né(e) à {lieu_naiss}, le {date_naiss}, '
                f'a validé les épreuves du programme de la <b>{niveau}</b> à la section '
                f'<b>{section}</b>, Option <b>{option}</b> de l\'année académique <b>{annee}</b>.'
            )
        elif self.type_attestation == 'stage':
            corps = (
                f'Je soussigné, {signataire}, atteste par la présente que le (la) nommé(e) '
                f'<b>{nom_aff}</b>, né(e) à {lieu_naiss}, le {date_naiss}, '
                f'a effectué un stage dans le cadre du programme de la <b>{niveau}</b> '
                f'à la section <b>{section}</b>, Option <b>{option}</b> '
                f"de l'année académique <b>{annee}</b>."
            )
        else:
            corps = (
                f'Je soussigné, {signataire}, atteste par la présente que le (la) nommé(e) '
                f'<b>{nom_aff}</b>, né(e) à {lieu_naiss}, le {date_naiss}, suit les cours inscrits '
                f'au programme de la <b>{niveau}</b> à la section <b>{section}</b>, '
                f'Option <b>{option}</b> de l\'année académique <b>{annee}</b>.'
            )

        return corps, CLOTURE_ATTESTATION

    def _body_story(self):
        corps, cloture = self._build_body_parts()
        story = [Paragraph(corps, self._body_style())]
        if cloture:
            story.append(Paragraph(cloture, self._cloture_style()))
        return story

    def _draw_body(self, c, x, width, y_top, y_bottom_max) -> float:
        """Dessine le corps dans la zone haute, sans empiéter sur la signature."""
        story = self._body_story()
        y_cursor = y_top
        for i, para in enumerate(story):
            if i > 0:
                y_cursor -= GAP_LIGNE_BLANCHE_AVANT_CLOTURE
            remaining = y_cursor - y_bottom_max
            if remaining <= 0:
                break
            _w, h = para.wrap(width, remaining)
            para.drawOn(c, x, y_cursor - h)
            y_cursor -= h
        return y_cursor

    def _draw_signature(self, c, width, y_top):
        """Bloc signature à position fixe (sous le corps)."""
        x_right = width - MARGIN_LR
        date_str = date.today().strftime('%d/%m/%Y')
        c.setFillColor(INK)

        y_cursor = y_top
        c.setFont(att_fond.FONT_CORPS, SIGNATURE_FONT_SIZE)
        secretaire_line = 'Le Secrétaire Général Académique,'
        date_line = f'Fait à {self.lieu_delivrance}, le {date_str}'
        sec_w = c.stringWidth(secretaire_line, att_fond.FONT_CORPS, SIGNATURE_FONT_SIZE)
        cx_secretaire = x_right - sec_w / 2
        c.drawCentredString(cx_secretaire, y_cursor, date_line)
        y_cursor -= SIGNATURE_LINE_H

        c.drawRightString(x_right, y_cursor, secretaire_line)
        y_cursor -= SIGNATURE_LINE_H + SIGNATURE_GAP_BEFORE_NOM

        c.setFont(att_fond.FONT_CORPS_GRAS, SIGNATURE_NOM_FONT_SIZE)
        nom_w = c.stringWidth(SIGNATAIRE_NOM, att_fond.FONT_CORPS_GRAS, SIGNATURE_NOM_FONT_SIZE)
        x_nom_left = x_right - nom_w
        c.drawRightString(x_right, y_cursor, SIGNATAIRE_NOM)
        y_nom = y_cursor

        c.setStrokeColor(INK)
        c.setLineWidth(0.5)
        c.line(x_nom_left, y_nom - 4, x_right, y_nom - 4)
        y_cursor -= SIGNATURE_LINE_H

        c.setFont(att_fond.FONT_CORPS, SIGNATURE_FONCTION_FONT_SIZE)
        c.drawCentredString(x_nom_left + nom_w / 2, y_cursor, SIGNATAIRE_FONCTION)

    def _draw_numero(self, c, width):
        x_left = MARGIN_LR
        x_right = width - MARGIN_LR
        y_footer = Y_PIED_PAGE

        c.setFillColor(INK)
        c.setFont('Helvetica-Bold', PIED_MENTION_FONT_SIZE)
        c.drawString(x_left, y_footer, 'SANS RATURE NI SURCHARGE')
        c.setFont(FONT_PIED, PIED_NUMERO_FONT_SIZE)
        c.drawRightString(x_right, y_footer, f'N° AFE {_numero_afe(self.attestation)}')

        y_qr_bottom = y_footer + PIED_MENTION_FONT_SIZE + QRCODE_GAP_FOOTER
        _draw_qrcode(c, x_left, y_qr_bottom, _attestation_qr_payload(self.attestation), QRCODE_SIZE)
