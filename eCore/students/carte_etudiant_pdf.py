"""
Carte d'étudiant UNIKIN, PDF PVC ISO ID-1 (85,6 × 53,98 mm).
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
from students.carte_qr import student_qr_png

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


def build_carte_etudiant_filename(student) -> str:
    matricule = (student.numero_etudiant or "etudiant").replace("/", "-")
    return f"carte_etudiant_{matricule}.pdf"


def build_carte_etudiant_pdf(student, identification, annee_code) -> bytes:
    """Deux pages au format carte PVC, prêtes pour l'imprimante à badges."""
    buffer = BytesIO()
    page = pdf_canvas.Canvas(buffer, pagesize=(CARD_W, CARD_H))
    page.setTitle(f"Carte d'étudiant {student.numero_etudiant}")
    page.setAuthor(institution_nom_majuscules())
    _draw_recto(page, 0, 0, student, identification, annee_code or "")
    page.showPage()
    _draw_verso(page, 0, 0, student, annee_code or "")
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


def _photo_reader(student):
    photo = getattr(student, "photo", None)
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


def _draw_photo(page, student, x, y, w, h):
    page.setFillColor(PHOTO_BG)
    page.rect(x, y, w, h, stroke=0, fill=1)
    reader = _photo_reader(student)
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
        initiales = ((student.prenom or " ")[:1] + (student.nom or " ")[:1]).upper().strip() or "ET"
        page.setFillColor(BLUE)
        page.setFont("Helvetica-Bold", 11)
        page.drawCentredString(x + w / 2, y + h / 2 - 3, initiales)
    page.setStrokeColor(BLUE)
    page.setLineWidth(0.7)
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


def _shown(value):
    text = (value or "").strip()
    return bool(text) and text != "—"


def _draw_recto(page, x, y, student, identification, annee):
    top = y + CARD_H
    page.saveState()
    _clip_card(page, x, y)
    page.setFillColor(colors.white)
    page.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)

    page.setFillColor(BLUE)
    page.rect(x, top - 8.2 * mm, CARD_W, 10 * mm, stroke=0, fill=1)
    page.setFillColor(YELLOW)
    page.rect(x, top - 9.3 * mm, CARD_W, 1.15 * mm, stroke=0, fill=1)
    page.setFillColor(RED)
    page.rect(x, top - 10.3 * mm, CARD_W, 1.05 * mm, stroke=0, fill=1)

    logo_w = _draw_logo(page, x + 2.2 * mm, top - 7.3 * mm, 5.6 * mm)
    text_x = x + 2.4 * mm + logo_w
    page.setFillColor(colors.white)
    page.setFont("Helvetica", 5)
    page.drawString(text_x, top - 3.15 * mm, PAYS.upper())
    page.setFont("Helvetica-Bold", 6.6)
    nom_univ = _ellipsize(page, institution_nom_majuscules(), "Helvetica-Bold", 6.6, CARD_W - logo_w - 22 * mm)
    page.drawString(text_x, top - 6.15 * mm, nom_univ)
    page.setFillColor(YELLOW)
    page.setFont("Helvetica-Bold", 8)
    page.drawRightString(x + CARD_W - 2.6 * mm, top - 5.3 * mm, institution_sigle())

    page.setFillColor(BLUE)
    page.rect(x, y, CARD_W, 6.4 * mm, stroke=0, fill=1)
    page.setFillColor(YELLOW)
    page.rect(x, y + 6.4 * mm, CARD_W, 0.7 * mm, stroke=0, fill=1)

    page.setFillColor(BLUE_BRIGHT)
    page.setFont("Helvetica-Bold", 10)
    page.drawCentredString(x + CARD_W / 2, top - 14.2 * mm, "CARTE D'ÉTUDIANT")

    photo_w = 22 * mm
    photo_h = 25.2 * mm
    photo_x = x + 2.6 * mm
    photo_y = y + 8.5 * mm
    _draw_photo(page, student, photo_x, photo_y, photo_w, photo_h)

    tx = photo_x + photo_w + 2.3 * mm
    max_w = x + CARD_W - 2.6 * mm - tx
    ty = photo_y + photo_h - 3.1 * mm

    nom = (student.nom or "—").upper()
    prenom = (student.prenom or "").strip()
    if prenom == "—":
        prenom = ""
    ty = _draw_lines(page, _wrap(page, nom, "Helvetica-Bold", 8, max_w, 2), tx, ty, "Helvetica-Bold", 8, INK, 3.3 * mm)
    if prenom:
        ty = _draw_lines(page, _wrap(page, prenom, "Helvetica", 7.5, max_w, 1), tx, ty - 0.3 * mm, "Helvetica", 7.5, INK, 3.1 * mm)
    if student.date_naissance:
        ne = student.date_naissance.strftime("%d/%m/%Y")
        sexe = "Né le" if student.sexe == "M" else "Née le" if student.sexe == "F" else "Né(e) le"
        ty = _draw_lines(page, [f"{sexe} {ne}"], tx, ty - 0.6 * mm, "Helvetica", 6, MUTED, 2.8 * mm)

    rows = []
    if _shown(identification.get("faculte")):
        rows.append((identification["faculte"], 2))
    if _shown(identification.get("filiere")):
        rows.append((identification["filiere"], 2))
    if _shown(identification.get("promotion")):
        rows.append((f"Promotion {identification['promotion']}", 1))
    if rows:
        ty -= 1.1 * mm
    fait_y = photo_y + 0.2 * mm
    for value, lines in rows:
        if ty < fait_y + 3.2 * mm:
            break
        ty = _draw_lines(
            page,
            _wrap(page, value, "Helvetica", 6, max_w, lines),
            tx,
            ty,
            "Helvetica",
            6,
            INK,
            2.6 * mm,
        )

    fait_le = timezone.localdate().strftime("%d/%m/%Y")
    page.setFillColor(INK)
    page.setFont("Helvetica-Oblique", 5.6)
    page.drawString(tx, fait_y, f"Fait à Kinshasa, le {fait_le}")

    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 7)
    page.drawString(x + 2.6 * mm, y + 2.3 * mm, student.numero_etudiant or "—")
    annee_label = f"Année {annee}" if annee else "Année académique"
    page.setFont("Helvetica", 6.5)
    page.drawRightString(x + CARD_W - 2.6 * mm, y + 2.35 * mm, annee_label)
    page.restoreState()


def _draw_verso(page, x, y, student, annee):
    top = y + CARD_H
    page.saveState()
    _clip_card(page, x, y)
    page.setFillColor(colors.white)
    page.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)

    page.setFillColor(BLUE)
    page.rect(x, top - 6.4 * mm, CARD_W, 8 * mm, stroke=0, fill=1)
    page.setFillColor(YELLOW)
    page.rect(x, top - 7.4 * mm, CARD_W, 1.05 * mm, stroke=0, fill=1)
    page.setFillColor(RED)
    page.rect(x, top - 8.3 * mm, CARD_W, 0.95 * mm, stroke=0, fill=1)

    page.setFillColor(colors.white)
    page.setFont("Helvetica-Bold", 6.2)
    page.drawString(x + 2.6 * mm, top - 4.2 * mm, institution_sigle())
    page.setFont("Helvetica", 5.5)
    page.drawRightString(x + CARD_W - 2.6 * mm, top - 4.1 * mm, "CARTE D'ÉTUDIANT")

    qr_size = 22 * mm
    qr_x = x + CARD_W - 2.6 * mm - qr_size
    qr_y = y + 12.2 * mm
    try:
        qr = ImageReader(BytesIO(student_qr_png(student, box_size=8)))
        page.drawImage(qr, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")
    except Exception:
        page.setStrokeColor(LINE)
        page.rect(qr_x, qr_y, qr_size, qr_size, stroke=1, fill=0)
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 5)
    page.drawCentredString(qr_x + qr_size / 2, qr_y - 2.4 * mm, "Scanner pour vérifier")

    text_w = qr_x - x - 5 * mm
    tx = x + 2.8 * mm
    ty = top - 12 * mm
    page.setFillColor(BLUE)
    page.setFont("Helvetica-Bold", 6.5)
    page.drawString(tx, ty, "Usage de la carte")
    ty -= 3.6 * mm
    mentions = [
        "Cette carte est personnelle et incessible.",
        "La présenter à tout contrôle universitaire.",
        "En cas de perte, aviser le Secrétariat général académique.",
        "Le QR code confirme l'authenticité de la carte.",
    ]
    if student.statut != "actif":
        mentions.append(f"Statut du dossier : {student.get_statut_display()}.")
    if annee:
        mentions.append(f"Validité liée à l'année {annee}.")
    for mention in mentions:
        ty = _draw_lines(
            page,
            _wrap(page, mention, "Helvetica", 5.4, text_w, 2),
            tx,
            ty,
            "Helvetica",
            5.4,
            INK,
            2.35 * mm,
        )
        ty -= 0.45 * mm

    page.setFillColor(MUTED)
    page.setFont("Helvetica", 4.8)
    page.drawString(tx, y + 8.6 * mm, str(student.code_unique))

    page.setFillColor(BLUE)
    page.rect(x, y, CARD_W, 6.6 * mm, stroke=0, fill=1)
    page.setFillColor(RED)
    page.rect(x, y + 6.6 * mm, CARD_W, 0.55 * mm, stroke=0, fill=1)
    page.setFillColor(colors.white)
    page.setFont("Helvetica", 5.6)
    page.drawCentredString(x + CARD_W / 2, y + 3.5 * mm, SIGNATAIRE_TITRE)
    page.setFont("Helvetica", 5)
    page.drawCentredString(x + CARD_W / 2, y + 1.5 * mm, institution_nom_majuscules())
    page.restoreState()
