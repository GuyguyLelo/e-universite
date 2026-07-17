"""Applique ecore-card-header et messages aux pages prestation restantes."""
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "eCore" / "templates" / "prestation"
files = [
    "calcul_paie.html",
    "etat_paie_mensuel.html",
    "bulletin_paie.html",
    "fiche_prestations_journaliere.html",
    "statistiques_prestations_enseignement.html",
    "cloture_paie_mensuelle.html",
    "prestation_mensuelle_saisie.html",
    "prestation_mensuelle_modifier.html",
    "prestation_depuis_horaire.html",
    "_budget_enveloppe.html",
]

MSG_OLD = """                {% if messages %}
                    {% for message in messages %}
                        <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}"""


def patch(text: str) -> str:
    text = text.replace(MSG_OLD, '                {% include "components/messages.html" %}')
    text = text.replace('<div class="card-header py-2">', '<div class="card-header ecore-card-header py-2">')
    text = text.replace('<div class="card-header d-flex', '<div class="card-header ecore-card-header d-flex')
    text = text.replace('<div class="card-header">', '<div class="card-header ecore-card-header">')
    text = text.replace("breadcrumb-item active", "breadcrumb-item f-w-400 active")
    text = text.replace(
        '<div class="alert alert-info mb-0">',
        '<div class="alert alert-info ecore-alert mb-0" role="alert">',
    )
    return text


for name in files:
    path = root / name
    if not path.exists():
        print("skip missing", name)
        continue
    orig = path.read_text(encoding="utf-8")
    new = patch(orig)
    if new != orig:
        path.write_text(new, encoding="utf-8")
        print("updated", name)
