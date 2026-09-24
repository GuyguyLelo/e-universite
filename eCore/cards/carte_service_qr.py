"""QR code de la carte de service, basé sur le code unique du personnel."""
import io
from urllib.parse import urljoin

import qrcode
from django.conf import settings
from django.urls import reverse


def personnel_card_url(personnel):
    path = reverse("cards:personnel_carte_public", kwargs={"code_unique": personnel.code_unique})
    base = getattr(settings, "CARD_PUBLIC_BASE_URL", None) or "http://127.0.0.1:8000/"
    if not base.endswith("/"):
        base += "/"
    return urljoin(base, path.lstrip("/"))


def personnel_qr_png(personnel, box_size=8):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(personnel_card_url(personnel))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#003E82", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
