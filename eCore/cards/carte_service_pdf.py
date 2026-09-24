"""
Carte de service UNIKIN, PDF PVC ISO ID-1 (85,6 × 53,98 mm).
Page 1 : recto. Page 2 : verso.
"""
from __future__ import annotations

import os
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from config.pdf_entete import (
    PAYS,
    SIGNATAIRE_TITRE,
    institution_logo_path,
    institution_nom_majuscules,
    institution_sigle,
)
from cards.carte_service_qr import personnel_qr_png

CARD_W = 85.6 * mm
CARD_H = 53.98 * mm

BLUE = colors.HexColor("#003E82")
BLUE_BRIGHT = colors.HexColor("#007FFF")
YELLOW = colors.HexColor("#F7D117")
RED = colors.HexColor("#CE1126")
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#475569")
LINE = colors.HexColor("#d6deea")
PHOTO_BG = colors.HexColor("#e8eef7")


def build_carte_service_filename(personnel) -> str:
    matricule = (personnel.matricule or f"personnel-{personnel.pk}").replace("/", "-")
    return f"carte_service_{matricule}.pdf"


def build_carte_service_pdf(personnel) -> bytes:
    """Deux pages au format carte PVC, prêtes pour l'imprimante à badges."""
    buffer = BytesIO()
    page = pdf_canvas.Canvas(buffer, pagesize=(CARD_W, CARD_H))
    page.setTitle(f"Carte de service {personnel.matricule or personnel.pk}")
    page.setAuthor(institution_nom_majuscules())
    _draw_recto(page, 0, 0, personnel)
    page.showPage()
    _draw_verso(page, 0, 0, personnel)
    page.showPage()
    page.save()
    return buffer.getvalue()


def _clip_card(page, x, y):
    path = page.beginPath()
    path.rect(x, y, CARD_W, CARD_H)
    page.clipPath(path, stroke=0, fill=0)


def _wrap(page, text, font, size, max_w, max_lines):
    words = " ".join((text or "—").split()).split(" ")
    lines = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if page.stringWidth(trial, font, size) <= max_w:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)
    if not lines:
        lines = ["—"]
    lines = lines[:max_lines]
    lines[-1] = _ellipsize(page, lines[-1], font, size, max_w)
    return lines


def _ellipsize(page, text, font, size, max_w):
    if page.stringWidth(text, font, size) <= max_w:
        return text
    trimmed = text
    while trimmed and page.stringWidth(trimmed + "...", font, size) > max_w:
        trimmed = trimmed[:-1]
    return (trimmed or "").rstrip() + "..."


def _draw_lines(page, lines, x, y, font, size, color, leading):
    page.setFillColor(color)
    page.setFont(font, size)
    for line in lines:
        page.drawString(x, y, line)
        y -= leading
    return y


def _grade_label(personnel):
    if getattr(personnel, "grade_id", None) and personnel.grade:
        return personnel.grade.nom
    return (personnel.grade_ancien or "").strip()


def _fonction_label(personnel):
    if getattr(personnel, "position_id", None) and personnel.position:
        return personnel.position.name
    return (personnel.function_quality or "").strip()


def _service_label(personnel):
    text = (personnel.assignment_service or "").strip()
    prefix = "Université de Kinshasa — "
    if text.startswith(prefix):
        text = text[len(prefix):].strip()
    return text


def _photo_reader(personnel):
    photo = getattr(personnel, "photo", None)
    if not photo or not getattr(photo, "name", None):
        return None
    try:
        path = photo.path
    except Exception:
        return None
    if not path or not os.path.isfile(path):
        return None
    try:
        return ImageReader(path)
    except Exception:
        return None


def _draw_photo(page, personnel, x, y, w, h):
    page.setFillColor(PHOTO_BG)
    page.rect(x, y, w, h, stroke=0, fill=1)
    reader = _photo_reader(personnel)
    if reader is not None:
        try:
            img_w, img_h = reader.getSize()
            scale = max(w / float(img_w), h / float(img_h))
            draw_w = img_w * scale
            draw_h = img_h * scale
            page.saveState()
            clip = page.beginPath()
            clip.rect(x, y, w, h)
            page.clipPath(clip, stroke=0, fill=0)
            page.drawImage(
                reader,
                x - (draw_w - w) / 2,
                y - (draw_h - h) / 2,
                width=draw_w,
                height=draw_h,
                mask="auto",
            )
            page.restoreState()
        except Exception:
            reader = None
    if reader is None:
        initiales = (
            (personnel.first_name or " ")[:1] + (personnel.last_name or " ")[:1]
        ).upper().strip() or "PS"
        page.setFillColor(BLUE)
        page.setFont("Helvetica-Bold", 11)
        page.drawCentredString(x + w / 2, y + h / 2 - 3, initiales)
    page.setStrokeColor(YELLOW)
    page.setLineWidth(1.1)
    page.rect(x, y, w, h, stroke=1, fill=0)


def _draw_logo(page, x, y, size):
    path = institution_logo_path()
    if not path:
        return 0
    try:
        reader = ImageReader(path)
        img_w, img_h = reader.getSize()
        scale = size / max(float(img_w), float(img_h))
        draw_w = img_w * scale
        draw_h = img_h * scale
        page.drawImage(
            reader,
            x,
            y + (size - draw_h) / 2,
            width=draw_w,
            height=draw_h,
            mask="auto",
            preserveAspectRatio=True,
        )
        return draw_w + 1.4 * mm
    except Exception:
        return 0


def _champ(page, label, value, x, y, label_w, value_w, max_lines=1):
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 5)
    page.drawString(x, y, label.upper())
    return _draw_lines(
        page,
        _wrap(page, value or "—", "Helvetica-Bold", 6.4, value_w, max_lines),
        x + label_w,
        y,
        "Helvetica-Bold",
        6.4,
        INK,
        2.5 * mm,
    )


def _draw_recto(page, x, y, personnel):
    """Bandeau vertical à gauche, photo dans le bandeau, identité à droite."""
    top = y + CARD_H
    page.saveState()
    _clip_card(page, x, y)
    page.setFillColor(colors.HexColor("#F4F7FB"))
    page.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)

    panel_w = 27 * mm
    page.setFillColor(BLUE)
    page.rect(x, y, panel_w, CARD_H, stroke=0, fill=1)
    page.setFillColor(YELLOW)
    page.rect(x + panel_w, y, 1.2 * mm, CARD_H, stroke=0, fill=1)
    page.setFillColor(RED)
    page.rect(x + panel_w + 1.2 * mm, y, 1.05 * mm, CARD_H, stroke=0, fill=1)

    _draw_logo(page, x + (panel_w - 6.4 * mm) / 2, top - 8.4 * mm, 6.4 * mm)
    photo_w = 19.5 * mm
    photo_h = 23.5 * mm
    photo_x = x + (panel_w - photo_w) / 2
    photo_y = y + 13.2 * mm
    _draw_photo(page, personnel, photo_x, photo_y, photo_w, photo_h)

    matricule = personnel.matricule or "—"
    page.setFillColor(YELLOW)
    page.setFont("Helvetica-Bold", 5.4)
    page.drawCentredString(
        x + panel_w / 2,
        y + 5.6 * mm,
        _ellipsize(page, matricule, "Helvetica-Bold", 5.4, panel_w - 2.4 * mm),
    )
    page.setFillColor(colors.white)
    page.setFont("Helvetica", 4.2)
    page.drawCentredString(x + panel_w / 2, y + 3.2 * mm, "MATRICULE")

    content_x = x + panel_w + 4.2 * mm
    content_r = x + CARD_W - 2.6 * mm
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 4.8)
    page.drawString(content_x, top - 3.8 * mm, PAYS.upper())
    page.setFillColor(BLUE)
    page.setFont("Helvetica-Bold", 6.2)
    page.drawString(
        content_x,
        top - 6.6 * mm,
        _ellipsize(page, institution_nom_majuscules(), "Helvetica-Bold", 6.2, content_r - content_x),
    )

    chip_y = top - 13.2 * mm
    chip_h = 5.4 * mm
    page.setFillColor(YELLOW)
    page.roundRect(content_x, chip_y, content_r - content_x, chip_h, 1.1 * mm, stroke=0, fill=1)
    page.setFillColor(BLUE)
    page.setFont("Helvetica-Bold", 8.2)
    page.drawCentredString((content_x + content_r) / 2, chip_y + 1.7 * mm, "CARTE DE SERVICE")

    categorie = personnel.category.name if personnel.category_id and personnel.category else ""
    ty = chip_y - 3.6 * mm
    if categorie:
        page.setFillColor(BLUE_BRIGHT)
        page.setFont("Helvetica", 5.2)
        page.drawString(content_x, ty, _ellipsize(page, categorie, "Helvetica", 5.2, content_r - content_x))
        ty -= 3.6 * mm

    nom = (personnel.last_name or "—").upper()
    prenom = (personnel.first_name or "").strip()
    identite = f"{prenom} {nom}".strip() if prenom else nom
    label_w = 15 * mm
    value_w = content_r - content_x - label_w
    for label, value, lines in (
        ("Nom", identite, 2),
        ("Grade", _grade_label(personnel) or "—", 1),
        ("Fonction", _fonction_label(personnel) or "—", 1),
        ("Service", _service_label(personnel) or "—", 2),
    ):
        ty = _champ(page, label, value, content_x, ty, label_w, value_w, lines)
        ty -= 1.15 * mm

    fait_le = timezone.localdate().strftime("%d/%m/%Y")
    page.setFillColor(INK)
    page.setFont("Helvetica-Oblique", 5.3)
    page.drawString(content_x, y + 2.3 * mm, f"Fait à Kinshasa, le {fait_le}")
    page.restoreState()


def _draw_verso(page, x, y, personnel):
    """Fond bleu, QR à gauche, mentions à droite, bandeau jaune en pied."""
    top = y + CARD_H
    page.saveState()
    _clip_card(page, x, y)
    page.setFillColor(BLUE)
    page.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)

    page.setFillColor(YELLOW)
    page.rect(x, top - 8.2 * mm, CARD_W, 10 * mm, stroke=0, fill=1)
    page.setFillColor(RED)
    page.rect(x, top - 9.1 * mm, CARD_W, 0.9 * mm, stroke=0, fill=1)
    page.setFillColor(BLUE)
    page.setFont("Helvetica-Bold", 8)
    page.drawCentredString(x + CARD_W / 2, top - 4.1 * mm, "CARTE DE SERVICE")
    page.setFont("Helvetica", 5)
    page.drawCentredString(x + CARD_W / 2, top - 6.6 * mm, institution_nom_majuscules())

    qr_size = 22 * mm
    qr_x = x + 4 * mm
    qr_y = y + 13.5 * mm
    page.setFillColor(colors.white)
    page.roundRect(qr_x - 1.4 * mm, qr_y - 1.4 * mm, qr_size + 2.8 * mm, qr_size + 2.8 * mm, 1.2 * mm, stroke=0, fill=1)
    try:
        qr = ImageReader(BytesIO(personnel_qr_png(personnel, box_size=8)))
        page.drawImage(qr, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")
    except Exception:
        page.setStrokeColor(LINE)
        page.rect(qr_x, qr_y, qr_size, qr_size, stroke=1, fill=0)
    page.setFillColor(YELLOW)
    page.setFont("Helvetica", 5)
    page.drawCentredString(qr_x + qr_size / 2, qr_y - 4 * mm, "Scanner pour vérifier")

    tx = qr_x + qr_size + 5 * mm
    text_w = x + CARD_W - 3 * mm - tx
    ty = top - 13.2 * mm
    page.setFillColor(YELLOW)
    page.setFont("Helvetica-Bold", 6.4)
    page.drawString(tx, ty, "Réservée au personnel")
    ty -= 3.8 * mm
    mentions = [
        "Carte personnelle et incessible.",
        "Elle atteste la qualité de l'agent.",
        "À présenter à tout contrôle.",
        "En cas de perte, aviser le Secrétariat général académique.",
    ]
    for mention in mentions:
        ty = _draw_lines(
            page,
            _wrap(page, mention, "Helvetica", 5.5, text_w, 2),
            tx,
            ty,
            "Helvetica",
            5.5,
            colors.white,
            2.4 * mm,
        )
        ty -= 0.55 * mm

    page.setFillColor(colors.HexColor("#D6E4F5"))
    page.setFont("Helvetica", 4.4)
    page.drawString(tx, y + 10.2 * mm, str(personnel.code_unique))

    page.setFillColor(YELLOW)
    page.rect(x, y, CARD_W, 7.4 * mm, stroke=0, fill=1)
    page.setFillColor(BLUE)
    page.setFont("Helvetica-Bold", 5.6)
    page.drawCentredString(x + CARD_W / 2, y + 4.2 * mm, SIGNATAIRE_TITRE)
    page.setFont("Helvetica", 5)
    page.drawCentredString(x + CARD_W / 2, y + 1.8 * mm, institution_sigle())
    page.restoreState()
