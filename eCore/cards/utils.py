"""Aperçu PNG de la carte de service UNIKIN pour le module Cartes PVC."""
from io import BytesIO

from django.core.files.base import ContentFile

from .carte_service_pdf import build_carte_service_pdf
from .models import Card


def _png_pages(personnel):
    import pymupdf

    pdf = build_carte_service_pdf(personnel)
    document = pymupdf.open(stream=pdf, filetype="pdf")
    zoom = 300 / 72
    matrix = pymupdf.Matrix(zoom, zoom)
    pages = []
    for index in range(min(2, document.page_count)):
        pixmap = document[index].get_pixmap(matrix=matrix, alpha=False)
        pages.append(pixmap.tobytes("png"))
    return pages


def generate_card_image(card_id, base_url=None):
    """Enregistre le recto et le verso de la carte de service UNIKIN."""
    card = Card.objects.select_related(
        "personnel__grade",
        "personnel__position",
        "personnel__category",
    ).get(id=card_id)
    if not card.personnel_id:
        raise ValueError("Cette carte n'est pas liée à un personnel.")

    recto, verso = _png_pages(card.personnel)
    if card.generated_card:
        card.generated_card.delete(save=False)
    if card.generated_card_back:
        card.generated_card_back.delete(save=False)
    card.generated_card.save(f"card_{card.id}_recto.png", ContentFile(recto), save=False)
    card.generated_card_back.save(f"card_{card.id}_verso.png", ContentFile(verso), save=True)
    return card.generated_card.url
