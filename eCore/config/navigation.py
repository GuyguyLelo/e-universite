"""
Détection du module / fonctionnalité actif pour le menu latéral e-Université.
"""

from __future__ import annotations

MAQUETTE_PATH_PREFIXES = (
    "/academics/semestres",
    "/academics/ues",
    "/academics/ecs",
)

MODULE_LABELS = {
    "structure": "Structure Académique",
    "maquette": "Maquette LMD",
    "students": "Gestion des Étudiants",
    "evaluations": "Évaluations & Notes",
    "prestation": "Gestion des prestations",
    "finance": "Gestion financière",
    "cards": "Gestion Personnel",
    "projets": "Projets tutorés réalisés",
    "documents": "Documents",
    "bibliotheque": "Bibliothèque Numérique",
    "admin": "Administration",
}


def get_active_module(request) -> str | None:
    """Retourne l'identifiant du module courant ou None (tableau de bord / hors module)."""
    if request is None:
        return None

    path = getattr(request, "path", "") or ""
    match = getattr(request, "resolver_match", None)

    if path.startswith("/admin"):
        return "admin"

    if path.startswith("/etablissements"):
        return "structure"

    if match is None:
        return None

    url_name = match.url_name or ""
    namespace = match.namespace or ""

    if url_name == "projets_tutores_realises":
        return "projets"

    if namespace == "projets":
        return "projets"

    if namespace == "students":
        return "students"
    if namespace == "evaluations" or namespace == "deliberations":
        return "evaluations"
    if namespace == "prestation":
        return "prestation"
    if namespace == "finance":
        return "finance"
    if namespace == "cards":
        return "cards"
    if namespace == "documents":
        if url_name in {
            "releve_notes_selection",
            "releve_notes_export_bulk",
            "generate_releve_notes",
            "grille_notes",
        } or path.startswith("/documents/releve-notes/") or path.startswith("/documents/grille"):
            return "evaluations"
        return "documents"
    if namespace == "bibliotheque":
        return "bibliotheque"

    if namespace == "academics":
        if any(path.startswith(prefix) for prefix in MAQUETTE_PATH_PREFIXES):
            return "maquette"
        if path.startswith("/academics/"):
            return "structure"

    # Comptes, mot de passe, page d'accueil sans module applicatif
    if url_name in {"home", "accueil", "dashboard", "login", "logout", "password_change"}:
        return None
    if path in ("", "/", "/accueil/", "/dashboard/") or path.startswith("/accounts/"):
        return None

    return None


def get_active_module_label(module: str | None) -> str:
    if not module:
        return "Navigation"
    return MODULE_LABELS.get(module, "Navigation")
