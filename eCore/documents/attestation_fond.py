"""
Fond vectoriel de l'attestation de fréquentation E.I.FI (ReportLab).
"""
from __future__ import annotations

import os
from collections import deque
from functools import lru_cache
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

# Bleu officiel E.I.FI (échantillonné sur le fond modèle)
BLUE = colors.HexColor('#0b3984')
BLUE_DARK = colors.HexColor('#003a9e')
BLUE_LIGHT = colors.HexColor('#5a78a8')
BLUE_PALE = colors.HexColor('#8fa8c8')
WHITE = colors.white

FONT_EDWARDIAN = 'Edwardian'
FONT_EDWARDIAN_SIZE = 26
FONT_ENTETE_PAYS_FALLBACK_SIZE = 13
FONT_ENTETE_MINISTERE_SIZE = 20
FONT_ENTETE_ECOLE_SIZE = 20
FONT_TITRE_SIZE = 19
FONT_TITRE_AUTRE_SIZE = 17
FONT_TITRE_DE_SIZE = 15
FONT_TITRE_DE_EDWARDIAN_SIZE = 18
FONT_ENTETE_PAYS_FALLBACK = 'Times-Italic'

# Polices du modèle officiel (ReportLab / PDF standard)
FONT_ENTETE_MINISTERE = 'Helvetica'
FONT_ENTETE_ECOLE = 'Helvetica-Bold'
FONT_TITRE = 'Times-Bold'
FONT_TITRE_DE = 'Times-Italic'
FONT_ARIAL = 'Arial'
FONT_ARIAL_BOLD = 'Arial-Bold'
FONT_CORPS = FONT_ARIAL
FONT_CORPS_GRAS = FONT_ARIAL_BOLD
FONT_PIED = 'Helvetica'

_edwardian_registered = False
_arial_registered = False


def _edwardian_font_paths():
    base = str(settings.BASE_DIR)
    yield os.path.join(base, 'documents', 'assets', 'fonts', 'EdwardianScriptITC.ttf')
    yield os.path.join(base, 'documents', 'assets', 'fonts', 'ITCEDSCR.TTF')
    yield r'C:\Windows\Fonts\ITCEDSCR.TTF'


def _register_edwardian_font() -> str:
    """Enregistre Edwardian Script ITC ; retourne le nom de police à utiliser."""
    global _edwardian_registered
    if _edwardian_registered:
        return FONT_EDWARDIAN
    for path in _edwardian_font_paths():
        if path and os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_EDWARDIAN, path))
            _edwardian_registered = True
            return FONT_EDWARDIAN
    return FONT_ENTETE_PAYS_FALLBACK


def font_entete_pays() -> str:
    return _register_edwardian_font()


def _arial_regular_paths():
    base = str(settings.BASE_DIR)
    yield os.path.join(base, 'documents', 'assets', 'fonts', 'arial.ttf')
    yield os.path.join(base, 'documents', 'assets', 'fonts', 'Arial.ttf')
    yield r'C:\Windows\Fonts\arial.ttf'


def _arial_bold_paths():
    base = str(settings.BASE_DIR)
    yield os.path.join(base, 'documents', 'assets', 'fonts', 'arialbd.ttf')
    yield os.path.join(base, 'documents', 'assets', 'fonts', 'Arial-Bold.ttf')
    yield r'C:\Windows\Fonts\arialbd.ttf'


def ensure_arial_fonts() -> tuple[str, str]:
    """Enregistre Arial pour le corps de texte ; retombe sur Helvetica si absent."""
    global _arial_registered, FONT_CORPS, FONT_CORPS_GRAS
    if _arial_registered:
        return FONT_CORPS, FONT_CORPS_GRAS

    regular_path = next((p for p in _arial_regular_paths() if p and os.path.exists(p)), None)
    bold_path = next((p for p in _arial_bold_paths() if p and os.path.exists(p)), None)

    if regular_path:
        pdfmetrics.registerFont(TTFont(FONT_ARIAL, regular_path))
        FONT_CORPS = FONT_ARIAL
    else:
        FONT_CORPS = 'Helvetica'

    if bold_path:
        pdfmetrics.registerFont(TTFont(FONT_ARIAL_BOLD, bold_path))
        FONT_CORPS_GRAS = FONT_ARIAL_BOLD
    else:
        FONT_CORPS_GRAS = 'Helvetica-Bold'

    if regular_path and bold_path:
        from reportlab.pdfbase.pdfmetrics import registerFontFamily

        registerFontFamily(
            FONT_ARIAL,
            normal=FONT_ARIAL,
            bold=FONT_ARIAL_BOLD,
        )

    _arial_registered = True
    return FONT_CORPS, FONT_CORPS_GRAS


def _fond_image_path():
    base = os.path.join(os.path.dirname(__file__), 'assets')
    for name in (
        'attestation_frequentation_fond.png',
        'fond_attest_freq.png',
        'attestation_frequentation_modele.png',
    ):
        path = os.path.join(base, name)
        if os.path.exists(path):
            return path
    return None


def _fond_image_reader(path: str) -> ImageReader:
    """Charge le fond PNG avec un peu plus de contraste (moins pâle à l'impression)."""
    try:
        from PIL import Image, ImageEnhance

        img = Image.open(path).convert('RGB')
        img = ImageEnhance.Contrast(img).enhance(1.45)
        img = ImageEnhance.Color(img).enhance(1.28)
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return ImageReader(buffer)
    except Exception:
        return ImageReader(path)


def draw_fond_frequentation(c: pdf_canvas.Canvas, width: float, height: float) -> bool:
    """Dessine le fond officiel en pleine page."""
    path = _fond_image_path()
    if not path:
        return False
    c.drawImage(
        _fond_image_reader(path),
        0,
        0,
        width=width,
        height=height,
        preserveAspectRatio=False,
        mask='auto',
    )
    return True


def _logo_path():
    base = str(settings.BASE_DIR)
    for parts in (
        ('static', 'images', 'logoeifi.png'),
        ('static', 'image', 'logoeifi.png'),
        ('assets', 'images', 'logoeifi.png'),
        ('media', 'logoeifi.png'),
        ('documents', 'assets', 'logoeifi.png'),
    ):
        path = os.path.join(base, *parts)
        if os.path.exists(path):
            return path
    return None


@lru_cache(maxsize=4)
def _logo_image_reader_cached(path: str, mtime_ns: int) -> ImageReader:
    """Supprime le fond blanc extérieur du logo (conserve le blanc du blason)."""
    from PIL import Image

    img = Image.open(path).convert('RGBA')
    w, h = img.size
    pixels = img.load()

    def is_outer_white(r, g, b, a):
        return a > 0 and r >= 235 and g >= 235 and b >= 235

    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if is_outer_white(*pixels[x, y]):
            queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        if not (0 <= x < w and 0 <= y < h):
            continue
        r, g, b, a = pixels[x, y]
        if not is_outer_white(r, g, b, a):
            continue
        visited.add((x, y))
        pixels[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)


def _logo_image_reader(path: str) -> ImageReader:
    return _logo_image_reader_cached(path, int(os.path.getmtime(path)))


class AttestationFondVectoriel:
    """Fond statique : image modèle officielle, ou dessin vectoriel de secours."""

    M_OUT = 0.95 * cm
    M_IN = 0.42 * cm

    def draw_entete(
        self,
        c: pdf_canvas.Canvas,
        width: float,
        height: float,
        *,
        titre: str,
        margin_top: float = 2.9 * cm,
        margin_h: float = 2.05 * cm,
        gap_avant_titre: float = 1.3 * cm,
        gap_titre_soulignement: float = 0.55 * cm,
        gap_apres_titre: float = 1.2 * cm,
    ) -> float:
        """En-tête institutionnel (sans bordures). Retourne Y sous le titre."""
        y = height - margin_top
        y = self._draw_header(c, width, y)
        y -= 0.25 * cm
        y = self._draw_logo(c, width, y)
        y -= gap_avant_titre
        y = self._draw_title(c, width, y, titre)
        y -= gap_titre_soulignement
        self._draw_title_flourish(c, width, y, margin_h=margin_h)
        return y - gap_apres_titre

    def draw(self, c: pdf_canvas.Canvas, width: float, height: float, *, titre: str = 'ATTESTATION DE FREQUENTATION'):
        self._draw_vector(c, width, height, titre=titre)

    def _draw_vector(self, c: pdf_canvas.Canvas, width: float, height: float, *, titre: str):
        from documents.attestation_border import draw_certificate_border

        draw_certificate_border(c, width, height, margin_out=self.M_OUT, margin_in=self.M_IN)
        y = height - self.M_OUT - self.M_IN - 0.15 * cm
        y = self._draw_header(c, width, y)
        y -= 0.35 * cm
        y = self._draw_logo(c, width, y)
        y -= 1.0 * cm
        y = self._draw_title(c, width, y, titre)
        y -= 0.55 * cm
        self._draw_title_flourish(c, width, y)
        self._draw_footer(c, width, height)

    def _draw_header(self, c, width, y):
        cx = width / 2
        c.setFillColor(BLUE)
        font_pays = font_entete_pays()
        size_pays = FONT_EDWARDIAN_SIZE if font_pays == FONT_EDWARDIAN else FONT_ENTETE_PAYS_FALLBACK_SIZE
        c.setFont(font_pays, size_pays)
        c.drawCentredString(cx, y, 'République Démocratique du Congo')
        y -= size_pays + 8
        c.setFont(FONT_ENTETE_MINISTERE, FONT_ENTETE_MINISTERE_SIZE)
        c.drawCentredString(cx, y, 'Enseignement Supérieur et Universitaire')
        y -= FONT_ENTETE_MINISTERE_SIZE + 5
        c.setFont(FONT_ENTETE_ECOLE, FONT_ENTETE_ECOLE_SIZE)
        c.drawCentredString(cx, y, 'Ecole Informatique des Finances')
        return y - 8

    def _draw_logo(self, c, width, y):
        path = _logo_path()
        logo_h = 19 * mm
        cx = width / 2
        if path:
            logo = _logo_image_reader(path)
            c.drawImage(
                logo, cx - logo_h * 0.55, y - logo_h,
                width=logo_h * 1.1, height=logo_h,
                preserveAspectRatio=True, mask='auto',
            )
            return y - logo_h - 2

        return self._draw_logo_shield(c, cx, y, logo_h)

    def _draw_logo_shield(self, c, cx, y, h):
        w = h * 0.85
        x0, y0 = cx - w / 2, y - h
        c.setLineWidth(1.0)
        c.setStrokeColor(BLUE_DARK)

        p = c.beginPath()
        p.moveTo(cx, y0 + h)
        p.lineTo(x0 + w, y0 + h * 0.72)
        p.lineTo(x0 + w, y0 + h * 0.22)
        p.curveTo(x0 + w, y0, cx, y0, cx, y0)
        p.curveTo(cx, y0, x0, y0, x0, y0 + h * 0.22)
        p.lineTo(x0, y0 + h * 0.72)
        p.close()
        c.setFillColor(BLUE_PALE)
        c.drawPath(p, stroke=1, fill=1)

        c.setFillColor(BLUE_LIGHT)
        c.rect(x0, y0 + h * 0.12, w / 2, h * 0.76, stroke=0, fill=1)
        c.setFillColor(BLUE_DARK)
        c.rect(cx, y0 + h * 0.12, w / 2, h * 0.76, stroke=0, fill=1)

        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', h * 0.16)
        c.drawCentredString(x0 + w * 0.25, y0 + h * 0.62, '★')
        c.setLineWidth(0.8)
        c.line(x0 + w * 0.18, y0 + h * 0.45, x0 + w * 0.32, y0 + h * 0.45)
        c.line(x0 + w * 0.25, y0 + h * 0.38, x0 + w * 0.25, y0 + h * 0.52)

        c.setFont('Times-Bold', h * 0.17)
        for i, letter in enumerate('EFI'):
            c.drawCentredString(x0 + w * 0.75, y0 + h * (0.58 - i * 0.18), letter)

        return y0 - 2

    def _is_frequentation_title(self, titre: str) -> bool:
        return titre.upper() == 'ATTESTATION DE FREQUENTATION'

    def _draw_title(self, c, width, y, titre: str):
        cx = width / 2
        c.setFillColor(BLUE)

        if self._is_frequentation_title(titre):
            left = 'ATTESTATION '
            de = 'De '
            right = 'FREQUENTATION'
            c.setFont(FONT_TITRE, FONT_TITRE_SIZE)
            w_left = c.stringWidth(left, FONT_TITRE, FONT_TITRE_SIZE)
            font_de = font_entete_pays()
            size_de = (
                FONT_TITRE_DE_EDWARDIAN_SIZE
                if font_de == FONT_EDWARDIAN
                else FONT_TITRE_DE_SIZE
            )
            w_de = c.stringWidth(de, font_de, size_de)
            w_right = c.stringWidth(right, FONT_TITRE, FONT_TITRE_SIZE)
            total = w_left + w_de + w_right
            x = cx - total / 2
            c.drawString(x, y, left)
            c.setFont(font_de, size_de)
            c.drawString(x + w_left, y + (3 if font_de == FONT_EDWARDIAN else 1), de)
            c.setFont(FONT_TITRE, FONT_TITRE_SIZE)
            c.drawString(x + w_left + w_de, y, right)
        else:
            c.setFont(FONT_TITRE, FONT_TITRE_AUTRE_SIZE)
            c.drawCentredString(cx, y, titre)
        return y

    def _draw_title_flourish(self, c, width, y, *, margin_h: float | None = None):
        margin = margin_h if margin_h is not None else self.M_OUT + self.M_IN + 1.6 * cm
        x1, x2 = margin, width - margin
        cx = width / 2
        gap = 1.05 * cm

        c.setStrokeColor(BLUE)
        c.setFillColor(BLUE)
        c.setLineWidth(0.55)
        c.line(x1, y, cx - gap, y)
        c.line(cx + gap, y, x2, y)

        c.setLineWidth(0.48)
        for sign in (-1, 1):
            p = c.beginPath()
            p.moveTo(cx + sign * 0.06 * cm, y)
            p.curveTo(
                cx + sign * 0.24 * cm, y + 0.2 * cm,
                cx + sign * 0.5 * cm, y + 0.1 * cm,
                cx + sign * 0.68 * cm, y - 0.04 * cm,
            )
            p.curveTo(
                cx + sign * 0.42 * cm, y - 0.17 * cm,
                cx + sign * 0.1 * cm, y - 0.1 * cm,
                cx + sign * 0.04 * cm, y,
            )
            c.drawPath(p, stroke=1, fill=0)

        for sign in (-1, 1):
            px = cx + sign * gap
            p = c.beginPath()
            p.moveTo(px, y)
            p.curveTo(
                px - sign * 0.14 * cm, y + 0.11 * cm,
                px - sign * 0.26 * cm, y + 0.02 * cm,
                px - sign * 0.1 * cm, y - 0.09 * cm,
            )
            c.drawPath(p, stroke=1, fill=0)

        c.circle(cx, y, 0.05 * cm, stroke=0, fill=1)

    def _draw_footer(self, c, width, height):
        x0 = self.M_OUT + self.M_IN + 0.35 * cm
        x1 = width - self.M_OUT - self.M_IN - 0.35 * cm
        y = self.M_OUT + self.M_IN + 0.28 * cm
        c.setFillColor(BLUE)
        c.setFont(FONT_PIED, 7)
        c.drawString(x0, y, 'SANS RATURE NI SURCHARGE')
        c.setFont(FONT_PIED, 9)
        c.drawRightString(x1, y, 'N° AFE .............../...........')
