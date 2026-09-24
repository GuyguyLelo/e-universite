"""Reçu de paiement, une page A4 noir et blanc, contenu resserré en haut."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as pdf_canvas

from config.pdf_entete import (
    DIRECTION_ACADEMIQUE,
    MINISTERE,
    PAYS,
    SIGNATAIRE_TITRE,
    institution_logo_path,
    institution_nom_majuscules,
    institution_sigle,
)

from .montant_lettres import montant_en_lettres
from .recu_qr import recu_qr_png


def build_recu_paiement_pdf(paiement) -> bytes:
    buffer = BytesIO()
    page = pdf_canvas.Canvas(buffer, pagesize=A4)
    page.setTitle(f'Reçu {paiement.reference}')
    page.setAuthor(institution_nom_majuscules())
    _draw(page, paiement)
    page.showPage()
    page.save()
    return buffer.getvalue()


def _parcours(inscription):
    classe = getattr(inscription, 'classe', None)
    promotion = getattr(classe, 'promotion', None) if classe else None
    filiere = getattr(promotion, 'filiere', None) if promotion else None
    faculte = None
    if filiere is not None:
        faculte = filiere.faculte
        if faculte is None and getattr(filiere, 'departement_id', None):
            faculte = filiere.departement.faculte
    return (
        faculte.nom if faculte else '—',
        filiere.nom if filiere else '—',
        promotion.nom if promotion else '—',
        (classe.nom or f'Classe {classe.code}') if classe else '—',
    )


def _logo_gris():
    path = institution_logo_path()
    if not path:
        return None
    try:
        from PIL import Image
        image = Image.open(path).convert('L')
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return ImageReader(buffer)
    except Exception:
        return path


def _draw(page, paiement):
    largeur, hauteur = A4
    inscription = paiement.inscription
    etudiant = inscription.etudiant
    motif = paiement.motif_paiement
    quand = timezone.localtime(paiement.date_paiement)
    faculte, filiere, promotion, classe = _parcours(inscription)
    gauche = 14 * mm
    droite = largeur - 14 * mm
    y = hauteur - 12 * mm

    logo = _logo_gris()
    if logo:
        page.drawImage(logo, gauche, y - 16 * mm, width=16 * mm, height=16 * mm, mask='auto', preserveAspectRatio=True)
        texte_x = gauche + 19 * mm
    else:
        texte_x = gauche
    page.setFillGray(0)
    page.setFont('Helvetica', 7)
    page.drawString(texte_x, y - 3 * mm, PAYS.upper())
    page.setFont('Helvetica-Bold', 8)
    page.drawString(texte_x, y - 7 * mm, MINISTERE.upper())
    page.setFont('Helvetica-Bold', 11)
    page.drawString(texte_x, y - 12 * mm, institution_nom_majuscules())
    page.setFont('Helvetica', 7)
    page.drawString(texte_x, y - 16 * mm, f'{DIRECTION_ACADEMIQUE}  ·  {institution_sigle()}')
    y -= 19 * mm
    y = _trait(page, gauche, droite, y)

    page.setFont('Helvetica-Bold', 12)
    page.drawCentredString(largeur / 2, y - 6 * mm, 'REÇU DE PAIEMENT')
    y -= 10 * mm
    annee = inscription.annee_academique.code if inscription.annee_academique_id else ''
    page.setFont('Helvetica', 8)
    page.drawString(gauche, y, f'Réf. {paiement.reference}')
    page.drawRightString(droite, y, f'{quand.strftime("%d/%m/%Y %H:%M")}   ·   {annee}')
    y -= 2 * mm
    y = _trait(page, gauche, droite, y)

    y = _ligne(page, gauche, y, 'Étudiant', f'{etudiant.prenom} {etudiant.nom}'.strip())
    y = _ligne(page, gauche, y, 'Matricule', etudiant.numero_etudiant)
    y = _ligne(page, gauche, y, 'Faculté', faculte)
    y = _ligne(page, gauche, y, 'Filière', filiere)
    y = _ligne(page, gauche, y, 'Promotion', f'{promotion}    ·    {classe}')
    y = _trait(page, gauche, droite, y)

    mode = paiement.get_mode_display()
    if paiement.operateur:
        mode = f'{mode} — {paiement.get_operateur_display()}'
    y = _ligne(page, gauche, y, 'Frais', f'{motif.nom} ({motif.code})')
    y = _ligne(page, gauche, y, 'Mode', mode)
    y = _ligne(page, gauche, y, 'Statut', paiement.get_statut_display())
    if paiement.telephone:
        y = _ligne(page, gauche, y, 'Numéro', paiement.telephone)
    if paiement.reference_transaction:
        y = _ligne(page, gauche, y, 'Transaction', paiement.reference_transaction)
    if paiement.carte_masquee:
        y = _ligne(page, gauche, y, 'Carte', f'•••• {paiement.carte_masquee}')
    y = _trait(page, gauche, droite, y)

    lettres = montant_en_lettres(paiement.montant, paiement.devise)
    page.setFont('Helvetica', 8)
    page.drawString(gauche, y - 4.5 * mm, 'Montant reçu')
    page.setFont('Helvetica-Bold', 12)
    page.drawRightString(droite, y - 4.8 * mm, paiement.montant_affiche)
    page.setFont('Helvetica-Oblique', 8)
    page.drawString(gauche, y - 9 * mm, lettres[:120].capitalize())
    y -= 11 * mm
    y = _trait(page, gauche, droite, y)
    y -= 4 * mm

    page.setFillGray(0)
    page.setFont('Helvetica', 8)
    page.drawString(gauche, y, f'Fait à Kinshasa, le {quand.strftime("%d/%m/%Y")}')
    page.setFont('Helvetica-Bold', 8)
    page.drawRightString(droite, y, SIGNATAIRE_TITRE)
    page.setFont('Helvetica', 7)
    page.drawRightString(droite, y - 4 * mm, institution_sigle())

    qr = ImageReader(BytesIO(recu_qr_png(paiement, box_size=4)))
    page.drawImage(qr, gauche, y - 22 * mm, width=16 * mm, height=16 * mm, mask='auto')
    page.setFont('Helvetica', 7)
    page.drawString(gauche + 18 * mm, y - 12 * mm, 'Scanner pour vérifier ce reçu.')
    page.setFont('Helvetica-Oblique', 7)
    page.drawString(gauche + 18 * mm, y - 16 * mm, 'Enregistrement du paiement dans e-Université.')


def _trait(page, gauche, droite, y):
    y -= 1.8 * mm
    page.setStrokeGray(0)
    page.setLineWidth(0.4)
    page.line(gauche, y, droite, y)
    return y - 1.6 * mm


def _ligne(page, x, y, label, valeur):
    y -= 4.4 * mm
    page.setFillGray(0.35)
    page.setFont('Helvetica', 8)
    page.drawString(x, y, label)
    page.setFillGray(0)
    page.setFont('Helvetica', 8)
    texte = str(valeur or '—')
    if pdfmetrics.stringWidth(texte, 'Helvetica', 8) > 140 * mm:
        texte = texte[:90] + '...'
    page.drawString(x + 28 * mm, y, texte)
    return y
