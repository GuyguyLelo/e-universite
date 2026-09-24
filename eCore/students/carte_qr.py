"""QR code de la carte étudiant, basé sur le code unique uuid4."""
import io
from urllib.parse import urljoin

import qrcode
from django.conf import settings
from django.urls import reverse


def student_card_url(student):
    """URL publique encodée dans le QR de la carte."""
    path = reverse("students:student_card_public", kwargs={"code_unique": student.code_unique})
    base = getattr(settings, "CARD_PUBLIC_BASE_URL", None) or "http://127.0.0.1:8000/"
    if not base.endswith("/"):
        base += "/"
    return urljoin(base, path.lstrip("/"))


def student_qr_png(student, box_size=8):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(student_card_url(student))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#003E82", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
