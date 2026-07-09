"""
Filigrane d'arrière-plan pâle pour les attestations E.I.FI.
"""
from __future__ import annotations

import math

from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas

from documents.attestation_fond import BLUE, BLUE_LIGHT

WATERMARK_STROKE_ALPHA = 0.12
WATERMARK_RING_ALPHA = 0.09
WATERMARK_TEXT_ALPHA = 0.10


def _clip_page_minus_zone(
    c: pdf_canvas.Canvas,
    width: float,
    height: float,
    inset: float,
    clear_x: float,
    clear_y: float,
    clear_w: float,
    clear_h: float,
):
    """Découpe la zone utile en excluant un rectangle (signature)."""
    p = c.beginPath()
    p.rect(inset, inset, width - 2 * inset, height - 2 * inset)
    p.rect(clear_x, clear_y, clear_w, clear_h)
    p._fillMode = 1  # even-odd : trou dans la zone de dessin
    c.clipPath(p, stroke=0, fill=1)


def _draw_pale_shield_outline(c: pdf_canvas.Canvas, cx: float, cy: float, h: float):
    """Contour de blason uniquement (sans remplissage carré)."""
    w = h * 0.85
    x0, y0 = cx - w / 2, cy - h / 2

    p = c.beginPath()
    p.moveTo(cx, y0 + h)
    p.lineTo(x0 + w, y0 + h * 0.72)
    p.lineTo(x0 + w, y0 + h * 0.22)
    p.curveTo(x0 + w, y0, cx, y0, cx, y0)
    p.curveTo(cx, y0, x0, y0, x0, y0 + h * 0.22)
    p.lineTo(x0, y0 + h * 0.72)
    p.close()

    c.setStrokeColor(BLUE)
    c.setStrokeAlpha(WATERMARK_STROKE_ALPHA)
    c.setLineWidth(0.9)
    c.drawPath(p, stroke=1, fill=0)

    c.setFillColor(BLUE)
    c.setFillAlpha(WATERMARK_TEXT_ALPHA)
    c.setFont('Times-Bold', h * 0.14)
    for i, letter in enumerate('EFI'):
        c.drawCentredString(x0 + w * 0.75, y0 + h * (0.58 - i * 0.18), letter)


def _draw_pale_rings(c: pdf_canvas.Canvas, cx: float, cy: float, max_radius: float):
    """Couronnes concentriques couvrant presque toute la page."""
    c.setStrokeColor(BLUE_LIGHT)
    c.setLineWidth(0.45)
    count = 5
    for i in range(count, 0, -1):
        radius = max_radius * i / count
        c.setStrokeAlpha(WATERMARK_RING_ALPHA * (0.75 + 0.25 * i / count))
        c.circle(cx, cy, radius, stroke=1, fill=0)


def _draw_pale_guilloche(c: pdf_canvas.Canvas, cx: float, cy: float, radius: float):
    """Motif ondulé discret."""
    c.setStrokeColor(BLUE)
    c.setStrokeAlpha(WATERMARK_RING_ALPHA * 0.85)
    c.setLineWidth(0.3)
    steps = 144
    for phase in (0, math.pi / 2):
        p = c.beginPath()
        for i in range(steps + 1):
            t = 2 * math.pi * i / steps
            r = radius + 0.22 * cm * math.sin(8 * t + phase)
            x = cx + r * math.cos(t)
            y = cy + r * math.sin(t)
            if i == 0:
                p.moveTo(x, y)
            else:
                p.lineTo(x, y)
        c.drawPath(p, stroke=1, fill=0)


def _draw_pale_sigle(c: pdf_canvas.Canvas, cx: float, cy: float, size: float):
    c.setFillColor(BLUE)
    c.setFillAlpha(WATERMARK_TEXT_ALPHA)
    c.setFont('Times-Bold', size)
    c.drawCentredString(cx, cy, 'E.I.FI')


def draw_pale_background_motif(
    c: pdf_canvas.Canvas,
    width: float,
    height: float,
    *,
    margin_out: float,
    margin_in: float,
    clear_x: float | None = None,
    clear_y: float | None = None,
    clear_w: float | None = None,
    clear_h: float | None = None,
):
    """Filigrane pâle sur presque toute la page, avec zone libre pour la signature."""
    inset = margin_out + margin_in + 0.18 * cm
    inner_w = width - 2 * inset
    inner_h = height - 2 * inset
    cx = width / 2
    cy = height / 2 + 0.4 * cm
    max_radius = min(inner_w, inner_h) * 0.48

    c.saveState()
    if clear_x is not None and clear_y is not None and clear_w and clear_h:
        _clip_page_minus_zone(c, width, height, inset, clear_x, clear_y, clear_w, clear_h)
    else:
        p = c.beginPath()
        p.rect(inset, inset, inner_w, inner_h)
        c.clipPath(p, stroke=0, fill=0)

    _draw_pale_rings(c, cx, cy, max_radius)
    _draw_pale_guilloche(c, cx, cy, max_radius * 0.88)
    _draw_pale_guilloche(c, cx, cy, max_radius * 0.62)
    _draw_pale_shield_outline(c, cx, cy + 0.2 * cm, min(inner_h * 0.42, 11.5 * cm))
    _draw_pale_sigle(c, cx, cy - max_radius * 0.2, 34)

    c.restoreState()
