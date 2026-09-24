"""
Composition du bureau du jury pour les délibérations (affichage, PV).
"""
from deliberations.constants import (
    ANNEE_JURY_M1_DEFAUT,
    FILIERES_JURY_M1_DEFAUT,
    JURY_BUREAU_M1_2526,
)


def _noms_membres_depuis_texte(texte: str) -> list[str]:
    if not texte:
        return []
    return [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]


def _nom_utilisateur(user) -> str:
    if not user:
        return ''
    return (user.get_full_name() or user.username or '').strip()


def est_promotion_master1_csi_rx(promotion) -> bool:
    if not promotion:
        return False
    filiere = getattr(promotion, 'filiere', None)
    code = (getattr(filiere, 'code', '') or '').strip().upper()
    return code in FILIERES_JURY_M1_DEFAUT


def libelle_promotion_jury(promotion) -> str:
    if not promotion:
        return 'MASTER 1'
    promo = (promotion.nom or promotion.code or '').strip()
    filiere_code = (getattr(getattr(promotion, 'filiere', None), 'code', '') or '').strip()
    promo_upper = promo.upper()
    filiere_upper = filiere_code.upper()
    if filiere_code and filiere_upper not in promo_upper:
        if 'MASTER' in promo_upper:
            return f'{promo} {filiere_code}'.upper()
        return f'{promo} MASTER {filiere_code}'.upper()
    return promo.upper()


def annee_academique_deliberation(deliberation) -> str:
    if not deliberation:
        return ANNEE_JURY_M1_DEFAUT
    for attr in ('annee_academique',):
        annee = getattr(deliberation, attr, None)
        if annee and getattr(annee, 'code', None):
            return annee.code
    session = getattr(deliberation, 'session', None)
    if session and getattr(session, 'annee_academique', None):
        return session.annee_academique.code
    return ANNEE_JURY_M1_DEFAUT


def valeurs_jury_m1_defaut() -> dict:
    return {
        'president': JURY_BUREAU_M1_2526['president'],
        'secretaire': JURY_BUREAU_M1_2526['secretaire'],
        'membres': list(JURY_BUREAU_M1_2526['membres']),
    }


def resoudre_composition_bureau(deliberation) -> dict:
    """
    Retourne president, secretaire, membres, promotion_label, annee_label.
    Champs texte de la délibération, puis comptes utilisateurs.
    """
    president = ''
    secretaire = ''
    membres = []

    if deliberation:
        president_nom = (getattr(deliberation, 'president_jury_nom', '') or '').strip()
        if president_nom:
            president = president_nom
        elif deliberation.president_jury_id:
            president = _nom_utilisateur(deliberation.president_jury) or president

        secretaire_nom = (getattr(deliberation, 'secretaire_jury_nom', '') or '').strip()
        if secretaire_nom:
            secretaire = secretaire_nom

        membres_texte = _noms_membres_depuis_texte(
            getattr(deliberation, 'membres_jury_noms', '') or '',
        )
        if membres_texte:
            membres = membres_texte
        else:
            jury_members = []
            for membre in deliberation.membres_jury.all().order_by('last_name', 'first_name', 'username'):
                nom = _nom_utilisateur(membre)
                if not nom:
                    continue
                if deliberation.president_jury_id and membre.pk == deliberation.president_jury_id:
                    continue
                jury_members.append(nom)
            if jury_members:
                membres = jury_members

    promotion = getattr(deliberation, 'promotion', None) if deliberation else None
    return {
        'president': president,
        'secretaire': secretaire,
        'membres': membres,
        'promotion_label': libelle_promotion_jury(promotion),
        'annee_label': annee_academique_deliberation(deliberation),
    }


def appliquer_jury_m1_defaut_sur_deliberation(deliberation, *, force: bool = False) -> bool:
    """Renseigne les champs texte du bureau jury M1 si vides (ou force)."""
    if not est_promotion_master1_csi_rx(deliberation.promotion):
        return False

    defaults = valeurs_jury_m1_defaut()
    changed = False

    if force or not (deliberation.president_jury_nom or '').strip():
        deliberation.president_jury_nom = defaults['president']
        changed = True
    if force or not (deliberation.secretaire_jury_nom or '').strip():
        deliberation.secretaire_jury_nom = defaults['secretaire']
        changed = True
    if force or not (deliberation.membres_jury_noms or '').strip():
        deliberation.membres_jury_noms = '\n'.join(defaults['membres'])
        changed = True

    if changed:
        deliberation.save(update_fields=[
            'president_jury_nom', 'secretaire_jury_nom', 'membres_jury_noms', 'updated_at',
        ])
    return changed
