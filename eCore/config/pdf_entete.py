"""En-tête des rapports PDF, à partir de l'établissement pilote."""
import os

PAYS = 'République Démocratique du Congo'
MINISTERE = 'Enseignement Supérieur et Universitaire'
SIGNATAIRE_TITRE = 'Secrétaire Général Académique'
DIRECTION_ACADEMIQUE = 'SECRÉTARIAT GÉNÉRAL ACADÉMIQUE'


def etablissement_pilote():
    from config.models import Etablissement

    try:
        return Etablissement.get_pilote()
    except Exception:
        return None


def institution_nom():
    etab = etablissement_pilote()
    nom = (getattr(etab, 'nom', None) or '').strip()
    return nom or 'Université de Kinshasa'


def institution_sigle():
    etab = etablissement_pilote()
    code = (getattr(etab, 'code', None) or '').strip()
    return code or 'UNIKIN'


def institution_nom_majuscules():
    return institution_nom().upper()


def institution_nom_article():
    """« l'Université de Kinshasa » pour les formules « de … »."""
    nom = institution_nom()
    if nom[:1].lower() in 'aeiouéèêëàâîïôûùyh':
        return f"l'{nom[0].lower()}{nom[1:]}"
    return f'le {nom}'


def signataire_phrase():
    return (
        f'{SIGNATAIRE_TITRE} '
        f'de {institution_nom_article()} ({institution_sigle()})'
    )


def institution_logo_path():
    """Chemin d'un logo lisible par ReportLab (PNG ou JPEG)."""
    etab = etablissement_pilote()
    logo = getattr(etab, 'logo', None)
    if not logo:
        return None
    try:
        path = logo.path
    except Exception:
        return None
    if not path or not os.path.isfile(path):
        return None
    if path.lower().endswith(('.png', '.jpg', '.jpeg')):
        return path
    png_path = os.path.splitext(path)[0] + '-pdf.png'
    try:
        if (
            not os.path.isfile(png_path)
            or os.path.getmtime(png_path) < os.path.getmtime(path)
        ):
            from PIL import Image
            Image.open(path).convert('RGBA').save(png_path, format='PNG')
    except Exception:
        return None
    return png_path
