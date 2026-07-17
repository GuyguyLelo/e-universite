"""
Génération PDF du brevet de formation continue — même style que l'attestation de fréquentation.
"""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
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
from documents.attestation_pdf import (
    BODY_FONT_SIZE,
    BODY_LEADING,
    FIRST_LINE_INDENT,
    INSTITUTION_NOM,
    INSTITUTION_SIGLE,
    PIED_MENTION_FONT_SIZE,
    PIED_NUMERO_FONT_SIZE,
    QRCODE_GAP_FOOTER,
    QRCODE_SIZE,
    SIGNATAIRE_FONCTION,
    SIGNATAIRE_NOM,
    SIGNATAIRE_TITRE,
    SIGNATURE_FONT_SIZE,
    SIGNATURE_FONCTION_FONT_SIZE,
    SIGNATURE_GAP_BEFORE_NOM,
    SIGNATURE_LINE_H,
    SIGNATURE_NOM_FONT_SIZE,
)

INK = BLUE

CLOTURE_BREVET = (
    'Le présent brevet lui est délivré pour faire valoir ce que de droit.'
)

# Mise en page paysage A4
PAGE_SIZE = landscape(A4)
MARGIN_LR = 2.4 * cm
MARGIN_TOP_ENTETE = 1.6 * cm
GAP_AVANT_TITRE = 0.55 * cm
GAP_TITRE_SOULIGNEMENT = 0.35 * cm
GAP_APRES_TITRE = 0.55 * cm
GAP_CORPS_SIGNATURE = 0.35 * cm
GAP_LIGNE_BLANCHE_AVANT_CLOTURE = 14
Y_PIED_PAGE = 1.55 * cm
SIGNATURE_BLOCK_HEIGHT = (
    3 * SIGNATURE_LINE_H + SIGNATURE_GAP_BEFORE_NOM + SIGNATURE_FONCTION_FONT_SIZE + 8
)
Y_SIGNATURE_MIN = Y_PIED_PAGE + SIGNATURE_BLOCK_HEIGHT
Y_CORPS_BOTTOM_MAX = Y_SIGNATURE_MIN + GAP_CORPS_SIGNATURE


def _seminariste_display_name(seminariste) -> str:
    nom = (seminariste.nom or '').strip().upper()
    prenom = (seminariste.prenom or '').strip()
    if prenom:
        prenom = prenom[0].upper() + prenom[1:].lower() if len(prenom) > 1 else prenom.upper()
    parts = [p for p in (nom, prenom) if p]
    return ' '.join(parts) or '—'


def _slug_filename(text: str) -> str:
    text = re.sub(r'\s+', '_', (text or '').strip())
    text = re.sub(r'[^\w\-]', '', text, flags=re.UNICODE)
    return text or 'SEMINARISTE'


def build_brevet_filename(brevet) -> str:
    nom = _slug_filename(_seminariste_display_name(brevet.seminariste))
    numero = (brevet.numero or str(brevet.pk or 0)).replace('/', '-')
    return f'BREVET-FC-{nom}-{numero}.pdf'


def _public_base_url() -> str:
    configured = getattr(settings, 'CARD_PUBLIC_BASE_URL', None) or 'http://127.0.0.1:8000/'
    return configured.rstrip('/') + '/'


def _brevet_qr_payload(brevet) -> str:
    if brevet and brevet.pk:
        path = reverse('formation_continue:brevet_pdf', kwargs={'pk': brevet.pk})
        return urljoin(_public_base_url(), path.lstrip('/'))
    return urljoin(_public_base_url(), 'formation-continue/brevets/')


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


class BrevetGenerator:
    """Génère le brevet PDF (en-tête institutionnel + corps + signature)."""

    TITRE = 'BREVET DE FORMATION CONTINUE'

    def __init__(self, brevet, buffer=None, lieu_delivrance='Kinshasa'):
        self.brevet = brevet
        self.buffer = buffer if buffer else BytesIO()
        self.lieu_delivrance = lieu_delivrance or 'Kinshasa'
        self.date_delivrance = brevet.date_delivrance or date.today()

    def generate(self):
        ensure_arial_fonts()
        width, height = PAGE_SIZE
        c = pdf_canvas.Canvas(self.buffer, pagesize=PAGE_SIZE)

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
            titre=self.TITRE,
            margin_top=MARGIN_TOP_ENTETE,
            margin_h=MARGIN_LR + 0.6 * cm,
            gap_avant_titre=GAP_AVANT_TITRE,
            gap_titre_soulignement=GAP_TITRE_SOULIGNEMENT,
            gap_apres_titre=GAP_APRES_TITRE,
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
            'BrevetBody',
            fontName=att_fond.FONT_CORPS,
            fontSize=BODY_FONT_SIZE,
            leading=BODY_LEADING,
            alignment=TA_JUSTIFY,
            textColor=INK,
            firstLineIndent=FIRST_LINE_INDENT,
        )

    def _cloture_style(self):
        return ParagraphStyle(
            'BrevetCloture',
            parent=self._body_style(),
            firstLineIndent=FIRST_LINE_INDENT,
        )

    def _modules_label(self) -> str:
        modules = list(self.brevet.modules_valides.all().order_by('code'))
        if not modules:
            return 'les modules de formation aux TIC'
        if len(modules) == 1:
            return f'le module <b>{modules[0].code} — {modules[0].intitule}</b>'
        labels = [f'{m.code} — {m.intitule}' for m in modules]
        if len(labels) == 2:
            joined = f'{labels[0]} et {labels[1]}'
        else:
            joined = ', '.join(labels[:-1]) + f' et {labels[-1]}'
        return f'les modules <b>{joined}</b>'

    def _build_body_parts(self) -> tuple[str, str]:
        obs = (self.brevet.observations or '').strip()
        if obs:
            return obs.replace('\n', '<br/>'), CLOTURE_BREVET

        s = self.brevet.seminariste
        session = self.brevet.session
        nom_aff = _seminariste_display_name(s)
        type_label = s.get_type_participant_display()
        organisation = (s.organisation or '').strip()
        type_phrase = type_label
        if organisation:
            type_phrase = f'{type_label} ({organisation})'

        periode = (
            f'du {session.date_debut.strftime("%d/%m/%Y")} '
            f'au {session.date_fin.strftime("%d/%m/%Y")}'
        )
        signataire = (
            f'<b>{SIGNATAIRE_NOM}</b>, {SIGNATAIRE_TITRE} et {SIGNATAIRE_FONCTION} '
            f'de {INSTITUTION_NOM} ({INSTITUTION_SIGLE})'
        )
        modules_txt = self._modules_label()

        corps = (
            f'Je soussigné, {signataire}, certifie par la présente que le (la) nommé(e) '
            f'<b>{nom_aff}</b>, {type_phrase}, a suivi avec succès {modules_txt} '
            f'dans le cadre de la formation continue aux TIC, session '
            f'<b>{session.libelle}</b> ({periode}). '
            f'Au vu de ce qui précède, lui est délivré le présent brevet portant le n° '
            f'<b>{self.brevet.numero}</b>.'
        )
        return corps, CLOTURE_BREVET

    def _draw_body(self, c, x, width, y_top, y_bottom_max) -> float:
        corps, cloture = self._build_body_parts()
        story = [
            Paragraph(corps, self._body_style()),
            Paragraph(cloture, self._cloture_style()),
        ]
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
        x_right = width - MARGIN_LR
        date_str = self.date_delivrance.strftime('%d/%m/%Y')
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
        c.drawRightString(x_right, y_footer, f'N° BREVET {self.brevet.numero}')

        y_qr_bottom = y_footer + PIED_MENTION_FONT_SIZE + QRCODE_GAP_FOOTER
        _draw_qrcode(c, x_left, y_qr_bottom, _brevet_qr_payload(self.brevet), QRCODE_SIZE)


def generer_brevet_pdf(brevet, *, enregistrer=True):
    """Génère le PDF du brevet et l'enregistre sur le modèle."""
    brevet = (
        type(brevet).objects.select_related('seminariste', 'session')
        .prefetch_related('modules_valides')
        .get(pk=brevet.pk)
    )
    buffer = BytesIO()
    BrevetGenerator(brevet=brevet, buffer=buffer).generate()
    pdf_bytes = buffer.getvalue()
    filename = build_brevet_filename(brevet)

    if enregistrer:
        brevet.fichier.save(filename, ContentFile(pdf_bytes), save=False)
        brevet.updated_at = timezone.now()
        brevet.save(update_fields=['fichier', 'updated_at'])

    return pdf_bytes, filename
