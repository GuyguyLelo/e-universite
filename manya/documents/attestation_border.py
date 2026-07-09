"""
Bordures décoratives pour attestations — style certificat officiel.
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas

from documents.attestation_fond import BLUE, BLUE_DARK, BLUE_LIGHT


def _bezier_corner(c, s, flip_x=1, flip_y=1):
    """Motif d'angle : volutes symétriques (style diplôme / certificat)."""
    c.scale(flip_x, flip_y)

    def leaf(x0, y0, dx, dy):
        p = c.beginPath()
        p.moveTo(x0, y0)
        p.curveTo(x0 + dx * 0.4, y0 + dy * 0.15, x0 + dx * 0.85, y0 + dy * 0.55, x0 + dx, y0 + dy * 0.25)
        p.curveTo(x0 + dx * 0.65, y0 + dy * 0.95, x0 + dx * 0.15, y0 + dy, x0, y0 + dy * 0.55)
        c.drawPath(p, stroke=1, fill=0)

    c.setLineWidth(0.75)
    leaf(0, 0, s, s)
    c.setLineWidth(0.55)
    leaf(s * 0.12, s * 0.12, s * 0.72, s * 0.72)

    c.setLineWidth(0.45)
    p = c.beginPath()
    p.moveTo(s * 0.05, s * 0.35)
    p.curveTo(s * 0.35, s * 0.05, s * 0.95, s * 0.15, s * 0.55, s * 0.55)
    c.drawPath(p, stroke=1, fill=0)

    for px, py, r in (
        (s * 0.42, s * 0.42, s * 0.045),
        (s * 0.18, s * 0.72, s * 0.032),
        (s * 0.68, s * 0.22, s * 0.028),
    ):
        c.circle(px, py, r, stroke=0, fill=1)


def _side_flourish(c, s):
    """Ornement latéral (milieu gauche / droite)."""
    c.setLineWidth(0.55)
    p = c.beginPath()
    p.moveTo(0, s * 0.9)
    p.curveTo(s * 0.55, s * 0.45, s * 0.45, -s * 0.45, 0, -s * 0.85)
    p.curveTo(-s * 0.35, -s * 0.55, -s * 0.25, s * 0.25, 0, s * 0.45)
    c.drawPath(p, stroke=1, fill=0)
    c.circle(0, s * 0.55, s * 0.04, stroke=0, fill=1)
    c.circle(0, -s * 0.45, s * 0.03, stroke=0, fill=1)


def _top_bottom_flourish(c, s):
    """Ornement centré (haut / bas de page)."""
    c.setLineWidth(0.5)
    p = c.beginPath()
    p.moveTo(-s * 1.15, 0)
    p.curveTo(-s * 0.35, s * 0.32, s * 0.35, s * 0.32, s * 1.15, 0)
    c.drawPath(p, stroke=1, fill=0)
    for px in (-s * 0.52, 0, s * 0.52):
        c.circle(px, 0, s * 0.038, stroke=0, fill=1)


def draw_certificate_border(
    c: pdf_canvas.Canvas,
    width: float,
    height: float,
    *,
    margin_out: float,
    margin_in: float,
):
    """Double cadre + fleurons aux angles et sur les côtés."""
    o, i = margin_out, margin_out + margin_in
    inner_gap = i + 0.12 * cm

    for inset, lw, color in (
        (o, 2.0, BLUE),
        (i, 1.0, BLUE),
        (inner_gap, 0.35, BLUE_LIGHT),
    ):
        c.setStrokeColor(color)
        c.setLineWidth(lw)
        c.rect(inset, inset, width - 2 * inset, height - 2 * inset, stroke=1, fill=0)

    c.setStrokeColor(BLUE)
    c.setFillColor(BLUE)
    corner_size = 1.15 * cm
    corners = (
        (o, height - o, 1, -1),
        (width - o, height - o, -1, -1),
        (o, o, 1, 1),
        (width - o, o, -1, 1),
    )
    for cx, cy, fx, fy in corners:
        c.saveState()
        c.translate(cx, cy)
        _bezier_corner(c, corner_size, fx, fy)
        c.restoreState()

    side_s = 0.55 * cm
    mid_y = height / 2
    for cx, flip in ((o, 1), (width - o, -1)):
        c.saveState()
        c.translate(cx, mid_y)
        c.scale(flip, 1)
        c.setStrokeColor(BLUE_LIGHT)
        c.setFillColor(BLUE_LIGHT)
        _side_flourish(c, side_s)
        c.restoreState()

    flourish_s = side_s * 1.1
    for cy, flip_y in ((height - o, -1), (o, 1)):
        c.saveState()
        c.translate(width / 2, cy)
        c.scale(1, flip_y)
        c.setStrokeColor(BLUE_LIGHT)
        c.setFillColor(BLUE_LIGHT)
        _top_bottom_flourish(c, flourish_s)
        c.restoreState()

    # filets d'angle intérieurs
    c.setStrokeColor(BLUE_DARK)
    c.setLineWidth(0.4)
    tick = 0.55 * cm
    for cx, cy, dx, dy in (
        (inner_gap, height - inner_gap, 1, -1),
        (width - inner_gap, height - inner_gap, -1, -1),
        (inner_gap, inner_gap, 1, 1),
        (width - inner_gap, inner_gap, -1, 1),
    ):
        c.line(cx, cy, cx + dx * tick, cy)
        c.line(cx, cy, cx, cy + dy * tick)
