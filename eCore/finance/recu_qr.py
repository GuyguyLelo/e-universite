"""QR du reçu de paiement : page publique de vérification."""
import io
from urllib.parse import urljoin

import qrcode
from django.conf import settings
from django.urls import reverse


def recu_public_url(paiement):
    path = reverse('finance:recu_public', kwargs={'reference': paiement.reference})
    base = getattr(settings, 'CARD_PUBLIC_BASE_URL', None) or 'http://127.0.0.1:8000/'
    if not base.endswith('/'):
        base += '/'
    return urljoin(base, path.lstrip('/'))


def recu_qr_png(paiement, box_size=8) -> bytes:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(recu_public_url(paiement))
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()
