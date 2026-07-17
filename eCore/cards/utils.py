import os
import logging
from io import BytesIO
from datetime import date
from urllib.parse import urljoin
from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .models import Card,CardSettings

logger = logging.getLogger(__name__)

# --- Helpers -----------------------------------------------------------------

def _safe_path(*parts):
    """Build an absolute path inside the project (BASE_DIR)."""
    base = getattr(settings, "BASE_DIR", None)
    if base is None:
        # Fallback: current file's directory (best effort)
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(str(base), *parts)


def _find_asset(*candidate_relative_paths):
    """Return first existing file among candidates, else None."""
    for rel in candidate_relative_paths:
        p = _safe_path(rel)
        if os.path.exists(p):
            return p
    return None


def _load_font(size, bold=False):
    # Try a few common fonts. You can drop your own fonts into static/fonts/.
    candidates = []
    if bold:
        candidates += [
            _find_asset("static", "fonts", "Montserrat-Bold.ttf"),
            _find_asset("static", "fonts", "Poppins-Bold.ttf"),
            _find_asset("static", "fonts", "Roboto-Bold.ttf"),
        ]
    else:
        candidates += [
            _find_asset("static", "fonts", "Montserrat-Regular.ttf"),
            _find_asset("static", "fonts", "Poppins-Regular.ttf"),
            _find_asset("static", "fonts", "Roboto-Regular.ttf"),
        ]

    # System fallbacks (Linux)
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass

    return ImageFont.load_default()


def _extract_brand_blues(logo_path):
    """
    Extract 2 blue-ish brand colors from the logo (best-effort).
    Returns: (primary_blue_rgb, accent_blue_rgb)
    """
    # Defaults close to EFI logo tones
    primary = (22, 35, 97)   # deep navy
    accent = (46, 98, 200)   # bright blue

    if not logo_path or not os.path.exists(logo_path):
        return primary, accent

    try:
        im = Image.open(logo_path).convert("RGBA")
        im = im.resize((96, 96), Image.LANCZOS)
        px = list(im.getdata())

        # Keep opaque pixels; ignore whites/near-blacks
        filtered = []
        for r, g, b, a in px:
            if a < 32:
                continue
            # ignore near white
            if r > 240 and g > 240 and b > 240:
                continue
            # ignore near black
            if r < 25 and g < 25 and b < 25:
                continue
            filtered.append((r, g, b))

        if not filtered:
            return primary, accent

        # Score pixels by "blue-ness": higher B relative to R/G and not too dark.
        def score(c):
            r, g, b = c
            return (b - (r + g) / 2.0) + (b / 255.0) * 20

        filtered.sort(key=score, reverse=True)
        top = filtered[:1500]

        # Build a small histogram of top colors (quantized)
        hist = {}
        for r, g, b in top:
            qr, qg, qb = (r // 8) * 8, (g // 8) * 8, (b // 8) * 8
            hist[(qr, qg, qb)] = hist.get((qr, qg, qb), 0) + 1

        # Pick the most frequent as accent candidate
        accent = max(hist.items(), key=lambda kv: kv[1])[0]

        # Primary = the "deeper" blue close to accent but darker
        darker = [
            c for c in filtered
            if c[2] > c[0] and c[2] > c[1] and (c[0] + c[1] + c[2]) < 380
        ]
        if darker:
            hist2 = {}
            for r, g, b in darker:
                qr, qg, qb = (r // 8) * 8, (g // 8) * 8, (b // 8) * 8
                hist2[(qr, qg, qb)] = hist2.get((qr, qg, qb), 0) + 1
            primary = max(hist2.items(), key=lambda kv: kv[1])[0]

        return tuple(primary), tuple(accent)
    except Exception:
        return primary, accent


def _circle_crop(im, size):
    im = im.convert("RGB")
    im = ImageOps.fit(im, (size, size), method=Image.LANCZOS, centering=(0.5, 0.2))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _draw_soft_gradient(img, primary, accent):
    """
    Simple diagonal gradient by alpha-blending two big polygons.
    Keeps it fast and avoids heavy numpy.
    """
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)

    # Top-right strong accent
    d.polygon([(w * 0.45, 0), (w, 0), (w, h * 0.45)], fill=(*accent, 210))
    # Bottom-left primary wash
    d.polygon([(0, h * 0.55), (0, h), (w * 0.55, h)], fill=(*primary, 180))
    # Center subtle band
    mid = (
        int((primary[0] + accent[0]) / 2),
        int((primary[1] + accent[1]) / 2),
        int((primary[2] + accent[2]) / 2),
    )
    d.polygon(
        [(w * 0.15, h * 0.15), (w * 0.85, h * 0.05), (w * 0.95, h * 0.85), (w * 0.05, h * 0.95)],
        fill=(*mid, 60),
    )

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _get_public_base_url(base_url=None):
    """Return the base URL used in QR code payloads."""
    if base_url:
        return base_url.rstrip("/") + "/"
    configured = getattr(settings, "CARD_PUBLIC_BASE_URL", None) or os.environ.get("CARD_PUBLIC_BASE_URL")
    if configured:
        return configured.rstrip("/") + "/"
    return "http://127.0.0.1:8000/"


# --- Main generator -----------------------------------------------------------

def generate_card_image(card_id, base_url=None):
    """
    Generates a professional EFI card (recto + verso) based on BRAND COLORS,
    without relying on recto.jpg / verso.jpg templates.

    Output: saves `generated_card` (recto) and `generated_card_back` (verso) as PNGs.
    """
    card = Card.objects.get(id=card_id)

    settings_row = CardSettings.objects.first()
    chief_title = (settings_row.training_division_chief_title if settings_row else "LE CHEF DE DIVISION FORMATION")
    chief_name = ((settings_row.training_division_chief_name or "") if settings_row else "")
    chief_sig_path = (
        settings_row.training_division_chief_signature.path
        if settings_row and settings_row.training_division_chief_signature and hasattr(settings_row.training_division_chief_signature, "path")
        else None
    )

    seal_path = (
        settings_row.digital_seal.path
        if settings_row and settings_row.digital_seal and hasattr(settings_row.digital_seal, "path")
        else None
    )

    today_str = "Kinshasa le : "+date.today().strftime("%d/%m/%Y")

    # PVC CR80 aspect @ 300dpi-ish
    WIDTH = 1016
    HEIGHT = 638

    # Assets
    logo_eifi = _find_asset(
        "static/image/logoeifi.png",
        "static/images/logoeifi.png",
        "media/logoeifi.png",
    )
    logo_min = _find_asset(
        "static/image/logomin.png",
        "static/images/logomin.png",
        "media/logomin.png",
    )

    primary, accent = _extract_brand_blues(logo_eifi)

    # ---------------- Recto ----------------
    recto = Image.new("RGB", (WIDTH, HEIGHT), (250, 251, 253))
    recto = _draw_soft_gradient(recto, primary, accent)
    dr = ImageDraw.Draw(recto)

    # White content card area
    pad = 44
    card_box = (pad, pad, WIDTH - pad, HEIGHT - pad)
    dr.rounded_rectangle(card_box, radius=26, fill=(255, 255, 255), outline=(230, 233, 240), width=2)

    # Top brand ribbon (diagonal)
    dr.polygon([(WIDTH - pad - 320, pad), (WIDTH - pad, pad), (WIDTH - pad, pad + 210)], fill=accent)
    dr.polygon([(WIDTH - pad - 450, pad), (WIDTH - pad - 250, pad), (WIDTH - pad, pad + 250), (WIDTH - pad, pad + 310)], fill=primary)

    # Logo EFI top-left
    if logo_eifi and os.path.exists(logo_eifi):
        lg = Image.open(logo_eifi).convert("RGBA")
        lg = ImageOps.contain(lg, (90, 90), Image.LANCZOS)
        recto.paste(lg, (pad + 28, pad + 26), lg)

    # Fonts
    font_title = _load_font(33, bold=True)
    font_meta = _load_font(24, bold=False)
    font_meta_b = _load_font(24, bold=True)

    # School name (fixed)
    title_x = pad + 130
    title_y = pad + 34
    dr.text((title_x, title_y), "ÉCOLE", font=font_title, fill=primary)
    dr.text((title_x, title_y + 54), "INFORMATIQUE DES FINANCES", font=_load_font(30, bold=True), fill=(30, 35, 50))

    # Name & position (from DB)
    full_name = f"{card.personnel.last_name} {card.personnel.first_name}".strip() or "Nom Prénom"
    
    # Calculate available width to avoid overlapping photo
    photo_size = 260
    photo_x = WIDTH - pad - photo_size - 90
    max_text_width = photo_x - (pad + 48) - 20
    
    name_font_size = 58
    name_font = _load_font(name_font_size, bold=True)
    bbox = dr.textbbox((0, 0), full_name, font=name_font)
    text_width = bbox[2] - bbox[0]
    
    while text_width > max_text_width and name_font_size > 24:
        name_font_size -= 2
        name_font = _load_font(name_font_size, bold=True)
        bbox = dr.textbbox((0, 0), full_name, font=name_font)
        text_width = bbox[2] - bbox[0]
        
    original_bbox = dr.textbbox((0, 0), "A", font=_load_font(58, bold=True))
    original_h = original_bbox[3] - original_bbox[1]
    current_h = bbox[3] - bbox[1]
    y_offset = (original_h - current_h) // 2 if current_h < original_h else 0

    dr.text((pad + 48, pad + 185 + y_offset), full_name, font=name_font, fill=accent)

    position = getattr(card.personnel.position, "name", "") if card.personnel.position else ""
    if position:
        chip_y = pad + 260
        
        pos_font_size = 28
        pos_font = _load_font(pos_font_size, bold=True)
        pos_bbox = dr.textbbox((0, 0), position, font=pos_font)
        pos_text_w = pos_bbox[2] - pos_bbox[0]
        
        while pos_text_w + 44 > max_text_width and pos_font_size > 16:
            pos_font_size -= 2
            pos_font = _load_font(pos_font_size, bold=True)
            pos_bbox = dr.textbbox((0, 0), position, font=pos_font)
            pos_text_w = pos_bbox[2] - pos_bbox[0]
            
        chip_w = max(360, pos_text_w + 44)
        if chip_w > max_text_width:
            chip_w = max_text_width
            
        dr.rounded_rectangle((pad + 48, chip_y, pad + 48 + chip_w, chip_y + 52), radius=14, fill=primary)
        
        pos_h = pos_bbox[3] - pos_bbox[1]
        text_y = chip_y + (52 - pos_h) // 2 - 4
        dr.text((pad + 70, text_y), position, font=pos_font, fill=(255, 255, 255))

    # -------- FIXED: Info list (icons aligned) + left accent bar extends --------
    left_x = pad + 64
    base_y = pad + 340
    line_h = 56

    category = getattr(card.personnel.category, "name", "") if card.personnel.category else ""
    edu = card.personnel.education_level or ""
    matricule = card.personnel.matricule or ""
    expiry = card.expiry_date.strftime("%d/%m/%Y") if card.expiry_date else ""

    info_rows = [
        ("Matricule", matricule),
        ("Catégorie", category),
        ("Niveau", edu),
        ("Expiration", expiry),
    ]

    sample = "Ag"
    bbox = dr.textbbox((0, 0), sample, font=font_meta)
    text_h = bbox[3] - bbox[1]

    bar_top = pad + 140
    list_bottom = base_y + (len(info_rows) - 1) * line_h + line_h
    bar_bottom = min(HEIGHT - pad - 24, list_bottom + 8)

    dr.rounded_rectangle((pad + 24, bar_top, pad + 34, bar_bottom), radius=6, fill=accent)

    for i, (k, v) in enumerate(info_rows):
        row_y = base_y + i * line_h
        center_y = row_y + line_h // 2
        text_y = row_y + (line_h - text_h) // 2

        dot_r = 10
        dot_cx = left_x - 17
        dr.ellipse((dot_cx - dot_r, center_y - dot_r, dot_cx + dot_r, center_y + dot_r), fill=accent)

        dr.text((left_x, text_y), f"{k} :", font=font_meta_b, fill=(40, 45, 60))
        dr.text((left_x + 150, text_y), v or "-", font=font_meta, fill=(40, 45, 60))
    # --------------------------------------------------------------------------

    # --- Rounded square photo (modern style) ---

    photo_size = 260
    photo_x = WIDTH - pad - photo_size - 90
    photo_y = pad + 190

    # Outer shadow (soft modern effect)
    shadow = Image.new("RGBA", (photo_size + 20, photo_size + 20), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (0, 0, photo_size + 20, photo_size + 20),
        radius=30,
        fill=(0, 0, 0, 60)
    )
    recto.paste(shadow, (photo_x - 10, photo_y - 10), shadow)

    # Frame border
    frame = Image.new("RGBA", (photo_size + 8, photo_size + 8), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle(
        (0, 0, photo_size + 8, photo_size + 8),
        radius=28,
        fill=(255, 255, 255),
        outline=accent,
        width=4
    )
    recto.paste(frame, (photo_x - 4, photo_y - 4), frame)

    # Load photo
    if card.personnel.photo and hasattr(card.personnel.photo, "path") and os.path.exists(card.personnel.photo.path):
        ph = Image.open(card.personnel.photo.path)
    else:
        ph = Image.new("RGB", (photo_size, photo_size), (235, 238, 245))
        pdraw = ImageDraw.Draw(ph)
        pdraw.rounded_rectangle(
            (40, 40, photo_size - 40, photo_size - 40),
            radius=20,
            outline=(200, 205, 220),
            width=6
        )

    # Fit image
    # We use centering=(0.5, 0.2) to favor the top of the photo (usually the head)
    ph = ImageOps.fit(ph, (photo_size, photo_size), method=Image.LANCZOS, centering=(0.5, 0.2))

    # Rounded mask
    mask = Image.new("L", (photo_size, photo_size), 0)
    m = ImageDraw.Draw(mask)
    m.rounded_rectangle(
        (0, 0, photo_size, photo_size),
        radius=26,
        fill=255
    )

    recto.paste(ph, (photo_x, photo_y), mask)

    #########
    # --- Chef des divisions (global) sous la photo ---
    info_top = photo_y + photo_size + 6
    info_left = photo_x
    info_w = photo_size

    font_chief = _load_font(18, bold=True)
    font_name = _load_font(20, bold=True)
    font_date = _load_font(16, bold=False)

    # 1) Titre
    dr.text((info_left, info_top), chief_title, font=font_chief, fill=primary)

    bbox = dr.textbbox((info_left, info_top), chief_title, font=font_chief)
    x1, y1, x2, y2 = bbox

    underline_y = y2 + 3
    dr.line(
        (x1, underline_y, x2, underline_y),
        fill=accent,
        width=2
    )

    # 2) Nom
    current_y = underline_y + 8
    if chief_name.strip():
        dr.text((info_left, current_y), chief_name.strip(), font=font_name, fill=(40, 45, 60))
        name_bbox = dr.textbbox((info_left, current_y), chief_name.strip(), font=font_name)
        current_y = name_bbox[3] + 6

    # 3) Sceau numérique : REMONTÉ au-dessus du nom / signature
    seal_bottom_y = current_y
    if seal_path and os.path.exists(seal_path):
        try:
            seal = Image.open(seal_path).convert("RGBA")
            seal = ImageOps.contain(seal, (110, 110), Image.LANCZOS)

            seal_x = info_left + (info_w - seal.size[0]) // 2

            # on remonte le sceau
            seal_y = max(info_top - 18, current_y - 82)

            recto.paste(seal, (seal_x, seal_y), seal)
            seal_bottom_y = seal_y + seal.size[1]
        except Exception:
            pass

    # 4) Signature : bien en dessous du sceau
    sig_bottom_y = current_y
    if chief_sig_path and os.path.exists(chief_sig_path):
        try:
            sig = Image.open(chief_sig_path).convert("RGBA")
            sig = ImageOps.contain(sig, (info_w, 42), Image.LANCZOS)
            sig_x = info_left + (info_w - sig.size[0]) // 2

            # la signature vient après le sceau
            sig_y = seal_bottom_y - 4 if seal_bottom_y > current_y else current_y + 6

            recto.paste(sig, (sig_x, sig_y), sig)
            sig_bottom_y = sig_y + sig.size[1]
        except Exception:
            pass

    # 5) Date du jour
    date_text = today_str
    date_y = min(sig_bottom_y + 4, HEIGHT - pad - 26)
    dr.text((info_left, date_y), date_text, font=font_date, fill=(70, 75, 90))


    #dr.text((WIDTH - pad - 260, HEIGHT - pad - 36), "Document interne EFI", font=_load_font(18, False), fill=(120, 125, 140))

       # ---------------- Verso (UPDATED alignment fix) ----------------
    verso = Image.new("RGB", (WIDTH, HEIGHT), (245, 246, 248))
    verso = _draw_soft_gradient(verso, primary, accent)
    dv = ImageDraw.Draw(verso)

    # content panel
    dv.rounded_rectangle(
        (pad, pad, WIDTH - pad, HEIGHT - pad),
        radius=26,
        fill=(255, 255, 255),
        outline=(230, 233, 240),
        width=2
    )

    # ----- TITRE VERSO -----
    ministry_text = "Ministère de l'Enseignement Supérieur, Universitaire,\nRecherche Scientifique et Innovations (ESURSI)"
    font_ministry = _load_font(20, bold=True)
    ministry_lines = ministry_text.split("\n")
    ministry_y = pad + 16
    for idx, line in enumerate(ministry_lines):
        bbox = dv.textbbox((0, 0), line, font=font_ministry)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        ministry_x = (WIDTH - text_w) // 2
        dv.text((ministry_x, ministry_y + idx * (text_h + 4)), line, font=font_ministry, fill=primary)

    title_text = "CARTE DE SERVICE"
    font_title_back = _load_font(48, bold=True)

    bbox = dv.textbbox((0, 0), title_text, font=font_title_back)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # centrer horizontalement
    title_x = (WIDTH - text_w) // 2

    # position verticale (au début du verso)
    title_y = pad + 72

    dv.text((title_x, title_y), title_text, font=font_title_back, fill=primary)

    # ===== SAME LINE ALIGNMENT SETTINGS =====
    row_top = pad + 148   # ligne commune QR + logo, légèrement abaissée
    qr_size = 220
    logo_max_size = 300   # augmenté

    # ---------- QR CODE (LEFT) ----------
    qr_x = pad + 100
    qr_y = row_top

    dv.rounded_rectangle(
        (qr_x - 16, qr_y - 16, qr_x + qr_size + 16, qr_y + qr_size + 16),
        radius=20,
        fill=(250, 251, 253),
        outline=(230, 233, 240),
        width=2
    )

    public_profile_path = reverse("cards:public_profile", kwargs={"public_token": str(card.public_token)})
    qr_payload = urljoin(_get_public_base_url(base_url), public_profile_path.lstrip("/"))

    try:
        import qrcode
    except ImportError as exc:
        # Fail loud in production instead of silently drawing "QR".
        # This makes missing dependency obvious on Linux servers.
        raise RuntimeError(
            "La librairie 'qrcode' n'est pas installée sur le serveur. "
            "Installez-la avec: pip install qrcode[pil]"
        ) from exc

    try:
        qr = qrcode.QRCode(version=2, box_size=6, border=2)
        qr.add_data(qr_payload)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_img = ImageOps.contain(qr_img, (qr_size, qr_size), Image.LANCZOS)
        verso.paste(qr_img, (qr_x, qr_y))
    except Exception as exc:
        logger.exception("Echec de generation du QR code pour la carte id=%s", card.id)
        raise RuntimeError(f"Echec de génération du QR code: {exc}") from exc

    # ---------- MINISTRY LOGO (RIGHT) ----------
    if logo_min and os.path.exists(logo_min):
        lm = Image.open(logo_min).convert("RGBA")

        # increase logo size
        lm = ImageOps.contain(lm, (logo_max_size, logo_max_size), Image.LANCZOS)

        lm_x = WIDTH - pad - 100 - lm.size[0]
        lm_y = row_top  # EXACT SAME Y as QR

        verso.paste(lm, (lm_x, lm_y), lm)

    # ---------- OFFICIAL SENTENCE BELOW ----------
    sentence = (
        "Les autorités tant civiles que militaires sont priées d'apporter aide et assistance "
        "au titulaire de la présente carte."
    )

    font_sentence = _load_font(28, bold=False)

    max_text_w = WIDTH - (pad * 2) - 120
    words = sentence.split()
    lines = []
    cur = ""

    for w in words:
        test = (cur + " " + w).strip()
        bb = dv.textbbox((0, 0), test, font=font_sentence)
        if (bb[2] - bb[0]) <= max_text_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w

    if cur:
        lines.append(cur)

    text_start_y = row_top + qr_size + 60
    y = text_start_y

    for ln in lines:
        bb = dv.textbbox((0, 0), ln, font=font_sentence)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        x = (WIDTH - tw) // 2
        dv.text((x, y), ln, font=font_sentence, fill=(55, 60, 75))
        y += th + 10

    # (REMOVED) Footer bar + "JUSTICE • PAIX • TRAVAIL"
    # Nothing added here, as requested.

    # ---------------- Save ----------------
    output_recto = BytesIO()
    recto.save(output_recto, format="PNG", optimize=True)

    output_verso = BytesIO()
    verso.save(output_verso, format="PNG", optimize=True)

    def _safe_clear_image(field_file):
        """Supprime le fichier media s'il existe, sans planter s'il est deja absent."""
        if not field_file:
            return
        name = getattr(field_file, "name", None) or ""
        if not name:
            return
        try:
            if field_file.storage.exists(name):
                field_file.storage.delete(name)
        except Exception:
            pass

    _safe_clear_image(card.generated_card)
    _safe_clear_image(card.generated_card_back)
    card.generated_card = None
    card.generated_card_back = None

    card.generated_card.save(f"card_{card.id}_recto.png", ContentFile(output_recto.getvalue()), save=False)
    card.generated_card_back.save(f"card_{card.id}_verso.png", ContentFile(output_verso.getvalue()), save=True)

    return card.generated_card.url