#!/usr/bin/env python3
"""Génère les formulaires modernisés e-Core."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "eCore" / "templates"

SKIP = {
    "academics/local_form.html",
    "academics/classe_form.html",
    "students/student_form.html",
    "students/inscription_form.html",
}


def field(name: str, col: str = "col-12", icon: str = "", required: bool = False, help_text: str = "", label: str = "", suffix: str = "") -> str:
    parts = [f'{{% include "components/ecore_form_field.html" with field=form.{name} col="{col}"']
    if icon:
        parts.append(f'icon="{icon}"')
    if required:
        parts.append("required=True")
    if help_text:
        parts.append(f'help="{help_text}"')
    if label:
        parts.append(f'label="{label}"')
    if suffix:
        parts.append(f'input_suffix="{suffix}"')
    parts.append("%}")
    return " ".join(parts)


def section(icon: str, title: str, subtitle: str, body: str, last: bool = False) -> str:
    cls = ' section_class="mb-0"' if last else ""
    return f"""{{% include "components/ecore_form_section_open.html" with icon="{icon}" title="{title}" subtitle="{subtitle}"{cls} %}}
{body}
{{% include "components/ecore_form_section_close.html" %}}"""


def aside_switch(field_name: str, title: str, hint: str) -> str:
    return f"""{{% include "components/ecore_form_aside_switch.html" with field=form.{field_name} title="{title}" hint="{hint}" %}}"""


def aside_tips(*tips: str) -> str:
    args = "".join(f' tip{i + 1}="{t}"' for i, t in enumerate(tips[:4]))
    return f'{{% include "components/ecore_form_aside_tips.html" with{args} %}}'


def render_form(
    path: str,
    breadcrumb_list: str,
    cancel_url: str,
    form_id: str,
    main_html: str,
    aside_html: str = "",
    full_width: bool = False,
    enctype: bool = False,
    extra_notices: str = "",
    extra_js: str = "",
    form_before: str = "",
) -> str:
    main_col = "col-lg-12" if full_width else "col-lg-8"
    aside_wrapper = "{% block form_aside_wrapper %}{% endblock %}" if full_width else f"""{{% block form_aside %}}
{aside_html}
{{% endblock %}}"""

    enctype_block = ' enctype="multipart/form-data"' if enctype else ""
    enctype_attr = f"{{% block form_enctype %}}{enctype_block}{{% endblock %}}" if enctype else ""

    return f"""{{% extends "components/ecore_form_base.html" %}}
{{% load static %}}

{{% block form_breadcrumb %}}
{breadcrumb_list}
{{% endblock %}}

{{% block form_id %}}{form_id}{{% endblock %}}
{enctype_attr}
{{% block form_extra_notices %}}
{extra_notices}
{{% endblock %}}

{{% block form_before_fields %}}
{form_before}
{{% endblock %}}

{{% block form_main_col %}}{main_col}{{% endblock %}}

{{% block form_main %}}
{main_html}
{{% endblock %}}

{{% block form_actions %}}
{{% url '{cancel_url}' as cancel_url %}}
{{% include "components/form_actions.html" with cancel_url=cancel_url %}}
{{% endblock %}}

{aside_wrapper}
{{% block form_extra_js %}}
{extra_js}
{{% endblock %}}
"""


def bc(items: list[tuple[str, str]]) -> str:
    lines = ['<li class="breadcrumb-item"><a href="{% url \'home\' %}"><i data-feather="home"></i></a></li>']
    for label, url_name in items:
        lines.append(f'<li class="breadcrumb-item"><a href="{{% url \'{url_name}\' %}}">{label}</a></li>')
    lines.append('<li class="breadcrumb-item f-w-400 active">{{ title }}</li>')
    return "\n".join(lines)


FORMS: dict[str, str] = {}

# --- Academics simple ---
def simple_entity(path, list_url, list_label, form_id, entity_label, active_hint, tips, has_description=True, parent=None):
    rows = []
    if parent:
        pname, picon = parent
        rows.append(f'<div class="row g-3">{field(pname, "col-md-6", picon, True)}</div>')
    rows.append(section(
        "fa-tag", "Identification", f"Code et nom de la {entity_label}",
        f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True)}
  {field("nom", "col-md-8", "fa-font", True)}
</div>""",
    ))
    if has_description:
        rows.append(section(
            "fa-align-left", "Description", "Informations complémentaires", field("description"), True
        ))
    aside = aside_switch("active", f"{entity_label.capitalize()} active", active_hint) + "\n" + aside_tips(*tips)
    FORMS[path] = render_form(
        path, bc([(list_label, list_url)]), list_url, form_id, "\n".join(rows), aside
    )


simple_entity(
    "academics/section_form.html", "academics:section_list", "Sections", "section-form",
    "section", "Visible dans la structure académique",
    ("Le code identifie le cycle (L, M, D…)", "Une section inactive n'apparaît plus dans les listes", "La description est optionnelle"),
)
simple_entity(
    "academics/faculte_form.html", "academics:faculte_list", "Facultés", "faculte-form",
    "faculté", "Visible dans l'organigramme",
    ("Le code faculté doit être unique", "Une faculté regroupe plusieurs départements", "La description précise le périmètre"),
)
simple_entity(
    "academics/departement_form.html", "academics:departement_list", "Départements", "departement-form",
    "département", "Visible sous la faculté parente",
    ("Rattachez le département à la bonne faculté", "Le code doit être unique", "La description est optionnelle"),
    parent=("faculte", "fa-university"),
)
simple_entity(
    "academics/filiere_form.html", "academics:filiere_list", "Filières", "filiere-form",
    "filière", "Proposable aux inscriptions",
    ("La filière dépend de la section", "Le code identifie la spécialité", "Une filière inactive est masquée"),
    parent=("section", "fa-sitemap"),
)
simple_entity(
    "academics/parcours_form.html", "academics:parcours_list", "Parcours", "parcours-form",
    "parcours", "Visible dans les choix de formation",
    ("Le parcours est rattaché à une filière", "Code et nom doivent être explicites", "La description aide à distinguer les parcours"),
    parent=("filiere", "fa-road"),
)

# Promotion
FORMS["academics/promotion_form.html"] = render_form(
    "academics/promotion_form.html",
    bc([("Promotions", "academics:promotion_list")]),
    "academics:promotion_list",
    "promotion-form",
    "\n".join([
        section("fa-sitemap", "Rattachement", "Filière et ordre dans le cursus", f"""<div class="row g-3">
  {field("filiere", "col-md-8", "fa-graduation-cap", True)}
  {field("ordre", "col-md-4", "fa-sort-numeric-asc", False, "Ordre d'affichage (1, 2, 3…)")}
</div>"""),
        section("fa-tag", "Identification", "Code et libellé de la promotion", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True, "Ex. P1, P2, P3")}
  {field("nom", "col-md-8", "fa-font", True, "Ex. Première année")}
</div>""", True),
    ]),
    aside_switch("active", "Promotion active", "Disponible pour les classes") + "\n" +
    aside_tips("La promotion définit l'année dans la filière", "L'ordre contrôle le tri dans les listes", "Une promotion inactive est masquée"),
)

# Annee academique
FORMS["academics/annee_academique_form.html"] = render_form(
    "academics/annee_academique_form.html",
    bc([("Années Académiques", "academics:annee_academique_list")]),
    "academics:annee_academique_list",
    "annee-form",
    "\n".join([
        section("fa-calendar", "Période", "Code et bornes de l'année universitaire", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True, "Ex. 2025-2026")}
  {field("annee_debut", "col-md-4", "fa-calendar-o", True)}
  {field("annee_fin", "col-md-4", "fa-calendar-check-o", True)}
</div>"""),
        section("fa-clock-o", "Dates officielles", "Début et fin de l'année académique", f"""<div class="row g-3">
  {field("date_debut", "col-md-6", "fa-play", True)}
  {field("date_fin", "col-md-6", "fa-stop", True)}
</div>""", True),
    ]),
    aside_switch("active", "Année active", "Une seule année active à la fois") + "\n" +
    '<div class="form-text small text-muted mb-3">{{ form.active.help_text }}</div>\n' +
    aside_tips("L'année active est utilisée par défaut partout", "Les dates cadrent les inscriptions et évaluations", "L'activation désactive les autres années"),
)

# Semestre
FORMS["academics/semestre_form.html"] = render_form(
    "academics/semestre_form.html",
    bc([("Semestres", "academics:semestre_list")]),
    "academics:semestre_list",
    "semestre-form",
    "\n".join([
        section("fa-sitemap", "Rattachement", "Promotion et numéro de semestre", f"""<div class="row g-3">
  {field("promotion", "col-md-8", "fa-graduation-cap", True)}
  {field("numero", "col-md-4", "fa-sort-numeric-asc", True)}
</div>"""),
        section("fa-tag", "Identification", "Code et nom (auto si vide)", f"""<div class="row g-3">
  {field("code", "col-md-6", "fa-hashtag", False, "Généré automatiquement si vide")}
  {field("nom", "col-md-6", "fa-font", False, "Généré automatiquement si vide")}
</div>"""),
        section("fa-star", "Crédits", "Charge ECTS du semestre", field("credits_ects", "col-md-4", "fa-star", True)),
        section("fa-calendar", "Calendrier", "Dates du semestre", f"""<div class="row g-3">
  {field("date_debut", "col-md-6", "fa-play")}
  {field("date_fin", "col-md-6", "fa-stop")}
</div>""", True),
    ]),
    aside_switch("active", "Semestre actif", "Visible dans la maquette") + "\n" +
    aside_tips("Le numéro ordonne les semestres dans la promotion", "Les crédits ECTS alimentent le LMD", "Les dates sont optionnelles mais utiles"),
)

# UE - full width
FORMS["academics/ue_form.html"] = render_form(
    "academics/ue_form.html",
    bc([("Unités d'Enseignement", "academics:ue_list")]),
    "academics:ue_list",
    "ue-form",
    "\n".join([
        section("fa-sitemap", "Rattachement", "Semestre et ordre d'affichage", f"""<div class="row g-3">
  {field("semestre", "col-md-8", "fa-calendar", True)}
  {field("ordre", "col-md-4", "fa-sort-numeric-asc")}
</div>"""),
        section("fa-tag", "Identification", "Code et nom de l'UE", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True)}
  {field("nom", "col-md-8", "fa-font", True)}
</div>"""),
        section("fa-calculator", "Paramètres LMD", "Crédits, coefficient et seuil", f"""<div class="row g-3">
  {field("credits_ects", "col-md-4", "fa-star", True)}
  {field("coefficient", "col-md-4", "fa-percent", True)}
  {field("seuil_validation", "col-md-4", "fa-check-circle", False, "Seuil sur 20")}
</div>"""),
        section("fa-align-left", "Description", "Contenu et objectifs", field("description")),
        section("fa-sliders", "Options", "Règles de validation LMD", f"""<div class="row g-3">
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Compensation</div><div class="text-muted small">Autorisée pour cette UE</div></div><div class="form-check form-switch mb-0">{{{{ form.compensation_autorisee }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Capitalisable</div><div class="text-muted small">Crédits conservables</div></div><div class="form-check form-switch mb-0">{{{{ form.capitalisable }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">UE active</div><div class="text-muted small">Visible dans la maquette</div></div><div class="form-check form-switch mb-0">{{{{ form.active }}}}</div></div></div>
</div>""", True),
    ]),
    full_width=True,
)

# EC - full width
FORMS["academics/ec_form.html"] = render_form(
    "academics/ec_form.html",
    bc([("Éléments Constitutifs", "academics:ec_list")]),
    "academics:ec_list",
    "ec-form",
    "\n".join([
        section("fa-sitemap", "Rattachement", "UE, professeur et ordre", f"""<div class="row g-3">
  {field("ue", "col-md-6", "fa-book", True)}
  {field("professeur", "col-md-4", "fa-user", False, "Repris dans les horaires")}
  {field("ordre", "col-md-2", "fa-sort-numeric-asc")}
</div>"""),
        section("fa-tag", "Identification", "Code et nom de l'EC", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True)}
  {field("nom", "col-md-8", "fa-font", True)}
</div>"""),
        section("fa-calculator", "Paramètres LMD", "Crédits, coefficient, volume et seuil", f"""<div class="row g-3">
  {field("credits_ects", "col-md-3", "fa-star", True)}
  {field("coefficient", "col-md-3", "fa-percent", True)}
  {field("volume_horaire", "col-md-3", "fa-clock-o", False, "Heures")}
  {field("seuil_validation", "col-md-3", "fa-check-circle", False, "Sur 20")}
</div>"""),
        section("fa-align-left", "Description", "Contenu de l'enseignement", field("description")),
        section("fa-sliders", "Options", "Règles de validation LMD", f"""<div class="row g-3">
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Compensation</div></div><div class="form-check form-switch mb-0">{{{{ form.compensation_autorisee }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Capitalisable</div></div><div class="form-check form-switch mb-0">{{{{ form.capitalisable }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">EC actif</div></div><div class="form-check form-switch mb-0">{{{{ form.active }}}}</div></div></div>
</div>""", True),
    ]),
    full_width=True,
)

# Type document
FORMS["students/type_document_form.html"] = render_form(
    "students/type_document_form.html",
    bc([("Types de Documents", "students:type_document_list")]),
    "students:type_document_list",
    "type-document-form",
    "\n".join([
        section("fa-tag", "Identification", "Code et nom du type", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True)}
  {field("nom", "col-md-8", "fa-font", True)}
</div>"""),
        section("fa-sort-numeric-asc", "Affichage", "Ordre dans la checklist dossier", field("ordre", "col-md-4", "fa-sort-numeric-asc")),
        section("fa-align-left", "Description", "Précisions pour l'agent", field("description"), True),
    ]),
    aside_switch("obligatoire", "Document obligatoire", "Requis pour un dossier complet") + "\n" +
    aside_switch("active", "Type actif", "Proposé dans les dossiers") + "\n" +
    aside_tips("L'ordre contrôle l'affichage dans le dossier", "Obligatoire = compte pour le statut Complet", "Un type inactif disparaît des checklists"),
)

# Document form - with enctype
FORMS["students/document_form.html"] = render_form(
    "students/document_form.html",
    bc([("Documents", "students:document_list")]),
    "students:document_list",
    "document-form",
    "\n".join([
        section("fa-user", "Étudiant", "Document rattaché à un étudiant", f"""<div class="row g-3">
  {field("etudiant", "col-md-6", "fa-user", True)}
  {field("type_document", "col-md-6", "fa-file-text", True)}
</div>"""),
        section("fa-link", "Inscription", "Lien optionnel avec une inscription", field("inscription", "col-md-6", "fa-graduation-cap")),
        section("fa-paperclip", "Fichier", "Pièce numérique jointe", field("fichier", "col-md-8", "fa-upload") + "\n{% if object and object.fichier %}<div class=\"mt-2\"><a href=\"{{ object.fichier.url }}\" target=\"_blank\" rel=\"noopener\">Voir le fichier actuel</a></div>{% endif %}"),
        section("fa-check", "Validation", "Contrôle administratif", """<div class="row g-3 align-items-center">
  <div class="col-md-6"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Document validé</div></div><div class="form-check form-switch mb-0">{{ form.valide }}</div></div></div>
</div>
""" + field("notes", "col-12", "fa-sticky-note", False, label="Notes"), True),
    ]),
    aside_tips("Le fichier peut être ajouté plus tard depuis le dossier", "L'inscription précise l'année concernée", "La validation confirme la conformité"),
    enctype=True,
)

# Evaluations
FORMS["evaluations/type_evaluation_form.html"] = render_form(
    "evaluations/type_evaluation_form.html",
    bc([("Types d'évaluation", "evaluations:type_evaluation_list")]),
    "evaluations:type_evaluation_list",
    "type-evaluation-form",
    "\n".join([
        section("fa-tag", "Identification", "Code et nom du type", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", True, "Ex. CC, TP, EXAM")}
  {field("nom", "col-md-8", "fa-font", True)}
</div>"""),
        section("fa-calculator", "Notation", "Coefficient et note maximale", f"""<div class="row g-3">
  {field("coefficient", "col-md-4", "fa-percent", True)}
  {field("note_max", "col-md-4", "fa-star", True, "Sur 20")}
  {field("ordre", "col-md-4", "fa-sort-numeric-asc")}
</div>"""),
        section("fa-align-left", "Description", "Usage du type d'évaluation", field("description"), True),
    ]),
    aside_switch("active", "Type actif", "Proposé lors de la création d'évaluations") + "\n" +
    aside_tips("Le coefficient pondère la moyenne", "La note max est généralement 20", "L'ordre organise les listes déroulantes"),
)

FORMS["evaluations/session_form.html"] = render_form(
    "evaluations/session_form.html",
    bc([("Sessions", "evaluations:session_list")]),
    "evaluations:session_list",
    "session-form",
    "\n".join([
        section("fa-sitemap", "Rattachement", "Semestre et numéro de session", f"""<div class="row g-3">
  {field("semestre", "col-md-8", "fa-calendar", True)}
  {field("numero", "col-md-4", "fa-sort-numeric-asc", True, "1 = S1, 2 = rattrapage")}
</div>"""),
        section("fa-tag", "Identification", "Code et nom (auto si vide)", f"""<div class="row g-3">
  {field("code", "col-md-6", "fa-hashtag", False, "Généré si vide")}
  {field("nom", "col-md-6", "fa-font", False, "Généré si vide")}
</div>"""),
        section("fa-calendar", "Calendrier", "Dates de la session", f"""<div class="row g-3">
  {field("date_debut", "col-md-4", "fa-play", True)}
  {field("date_fin", "col-md-4", "fa-stop", True)}
  {field("date_deliberation", "col-md-4", "fa-gavel")}
</div>""", True),
    ]),
    aside_switch("deliberation_faite", "Délibération effectuée", "Session déjà délibérée") + "\n" +
    aside_switch("verrouillee", "Session verrouillée", "Empêche les modifications") + "\n" +
    aside_switch("active", "Session active", "Visible dans les évaluations") + "\n" +
    aside_tips("Le numéro 2 correspond souvent au rattrapage", "Verrouillez après clôture des notes", "La date de délibération est optionnelle"),
)

FORMS["evaluations/evaluation_form.html"] = render_form(
    "evaluations/evaluation_form.html",
    bc([("Évaluations", "evaluations:evaluation_list")]),
    "evaluations:evaluation_list",
    "evaluation-form",
    "\n".join([
        section("fa-link", "Contexte", "EC, session et type", f"""<div class="row g-3">
  {field("ec", "col-md-4", "fa-book", True)}
  {field("session", "col-md-4", "fa-calendar", True)}
  {field("type_evaluation", "col-md-4", "fa-list", True)}
</div>"""),
        section("fa-tag", "Identification", "Code, nom et date", f"""<div class="row g-3">
  {field("code", "col-md-4", "fa-hashtag", False, "Auto si vide")}
  {field("nom", "col-md-4", "fa-font", False, "Auto si vide")}
  {field("date_evaluation", "col-md-4", "fa-calendar-check-o", True)}
</div>"""),
        section("fa-calculator", "Notation", "Coefficient et note max", f"""<div class="row g-3">
  {field("coefficient", "col-md-4", "fa-percent", True)}
  {field("note_max", "col-md-4", "fa-star", True)}
  {field("responsable", "col-md-4", "fa-user", False, "Enseignant responsable")}
</div>"""),
        section("fa-sticky-note", "Notes", "Observations internes", field("notes"), True),
    ]),
    aside_switch("active", "Évaluation active", "Ouverte à la saisie des notes") + "\n" +
    aside_tips("L'EC détermine la matière évaluée", "Le type fixe la nature (CC, examen…)", "Le responsable est optionnel"),
)

FORMS["evaluations/note_form.html"] = render_form(
    "evaluations/note_form.html",
    bc([("Notes", "evaluations:note_list")]),
    "evaluations:note_list",
    "note-form",
    "\n".join([
        section("fa-link", "Lien", "Étudiant et évaluation", f"""<div class="row g-3">
  {field("etudiant", "col-md-6", "fa-user", True)}
  {field("evaluation", "col-md-6", "fa-file-text", True)}
</div>"""),
        section("fa-calculator", "Résultat", "Note obtenue", f"""<div class="row g-3">
  {field("note", "col-md-4", "fa-star", False, "Laisser vide si absent")}
  {field("note_sur", "col-md-4", "fa-sliders", False, "Barème (défaut 20)")}
</div>"""),
        section("fa-info", "Absence", "Statut de présence", f"""<div class="row g-3">
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Absent</div></div><div class="form-check form-switch mb-0">{{{{ form.absent }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Justifié</div></div><div class="form-check form-switch mb-0">{{{{ form.justifie }}}}</div></div></div>
</div>
{field("justificatif", "col-12", "fa-align-left", False, "Motif d'absence")}
{field("notes", "col-12", "fa-sticky-note", False, "Remarques")}""", True),
    ]),
    aside_tips("Cochez absent si l'étudiant n'a pas composé", "La justification atténue l'absence", "La note est sur le barème de l'évaluation"),
)

# Deliberations
FORMS["deliberations/parametres_lmd_form.html"] = render_form(
    "deliberations/parametres_lmd_form.html",
    bc([("Paramètres LMD", "deliberations:parametres_lmd_list")]),
    "deliberations:parametres_lmd_list",
    "parametres-lmd-form",
    "\n".join([
        section("fa-graduation-cap", "Promotion", "Paramètres par promotion", field("promotion", "col-md-6", "fa-sitemap", True)),
        section("fa-check-circle", "Seuils", "Validation et crédits minimum", f"""<div class="row g-3">
  {field("seuil_validation", "col-md-6", "fa-star", True, "Moyenne sur 20")}
  {field("seuil_credits_minimum", "col-md-6", "fa-certificate", False, "Crédits pour valider")}
</div>"""),
        section("fa-sliders", "Compensation & capitalisation", "Règles LMD applicables", f"""<div class="row g-3">
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Compensation intra-UE</div></div><div class="form-check form-switch mb-0">{{{{ form.compensation_intra_ue }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Compensation intra-semestre</div></div><div class="form-check form-switch mb-0">{{{{ form.compensation_intra_semestre }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Compensation annuelle</div></div><div class="form-check form-switch mb-0">{{{{ form.compensation_annuelle }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Capitalisation UE</div></div><div class="form-check form-switch mb-0">{{{{ form.capitalisation_ue }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Capitalisation EC</div></div><div class="form-check form-switch mb-0">{{{{ form.capitalisation_ec }}}}</div></div></div>
  <div class="col-md-4"><div class="ecore-dossier-switch"><div><div class="fw-semibold small">Passage avec dettes</div></div><div class="form-check form-switch mb-0">{{{{ form.passage_avec_dettes }}}}</div></div></div>
</div>""", True),
    ]),
    aside_tips("Un jeu de paramètres par promotion", "Les seuils pilotent les délibérations", "Activez uniquement les compensations autorisées"),
)

FORMS["deliberations/deliberation_form.html"] = render_form(
    "deliberations/deliberation_form.html",
    bc([("Délibérations", "deliberations:deliberation_list")]),
    "deliberations:deliberation_list",
    "deliberation-form",
    "\n".join([
        section("fa-calendar", "Session", "Session et date", f"""<div class="row g-3">
  {field("session", "col-md-8", "fa-calendar", True)}
  {field("date_deliberation", "col-md-4", "fa-gavel", True)}
</div>"""),
        section("fa-users", "Jury", "Présidence et membres", f"""<div class="row g-3">
  {field("president_jury", "col-md-6", "fa-user", True)}
  {field("membres_jury", "col-md-6", "fa-users", False, "Maintenez Ctrl pour sélection multiple")}
</div>"""),
        section("fa-info", "Suivi", "Statut et compte-rendu", f"""<div class="row g-3">
  {field("statut", "col-md-4", "fa-flag", True)}
  {field("notes", "col-12", "fa-sticky-note", False, "Procès-verbal ou remarques")}
</div>""", True),
    ]),
    aside_tips("La session doit être prête pour délibérer", "Le président conduit la séance", "Le statut suit l'avancement"),
)

FORMS["deliberations/decision_jury_form.html"] = render_form(
    "deliberations/decision_jury_form.html",
    bc([("Décisions jury", "deliberations:decision_jury_list")]),
    "deliberations:decision_jury_list",
    "decision-jury-form",
    "\n".join([
        section("fa-link", "Contexte", "Délibération et étudiant", f"""<div class="row g-3">
  {field("deliberation", "col-md-4", "fa-gavel", True)}
  {field("etudiant", "col-md-4", "fa-user", True)}
  {field("inscription", "col-md-4", "fa-graduation-cap", True)}
</div>"""),
        section("fa-check", "Décision", "Résultat et mention", f"""<div class="row g-3">
  {field("decision", "col-md-4", "fa-flag", True)}
  {field("mention", "col-md-4", "fa-certificate")}
  {field("rang", "col-md-4", "fa-sort-numeric-asc")}
</div>"""),
        section("fa-calculator", "Résultats", "Moyenne et crédits", f"""<div class="row g-3">
  {field("moyenne_semestre", "col-md-4", "fa-star")}
  {field("credits_obtenus", "col-md-4", "fa-check-circle")}
  {field("credits_totaux", "col-md-4", "fa-book")}
</div>
{field("notes_jury", "col-12", "fa-sticky-note", False, "Observations du jury")}""", True),
    ]),
    aside_tips("L'inscription précise l'année concernée", "La mention est optionnelle", "Les crédits alimentent le relevé"),
)

# Prestation
FORMS["prestation/bareme_form.html"] = render_form(
    "prestation/bareme_form.html",
    bc([("Barèmes", "prestation:bareme_list")]),
    "prestation:bareme_list",
    "bareme-form",
    "\n".join([
        section("fa-tags", "Classification", "Type et période", f"""<div class="row g-3">
  {field("categorie", "col-md-6", "fa-tag", True, label="Type prestation")}
  {field("periode", "col-md-6", "fa-clock-o", True)}
</div>"""),
        section("fa-money", "Montant", "Intitulé et tarif", f"""<div class="row g-3">
  {field("intitule", "col-12", "fa-font", True)}
  {field("montant", "col-md-4", "fa-money", True, "Montant en CDF")}
  {field("ordre", "col-md-4", "fa-sort-numeric-asc")}
</div>""", True),
    ]),
    aside_switch("active", "Barème actif", "Utilisable pour les prestations") + "\n" +
    aside_tips("Le type détermine la catégorie de prestation", "L'ordre organise les listes", "Le montant est en francs congolais"),
)

FORMS["prestation/enveloppe_form.html"] = render_form(
    "prestation/enveloppe_form.html",
    bc([("Enveloppes", "prestation:enveloppe_list")]),
    "prestation:enveloppe_list",
    "enveloppe-form",
    section("fa-money", "Budget", "Période et montant alloué", f"""<div class="row g-3">
  {field("annee", "col-md-4", "fa-calendar", True)}
  {field("mois", "col-md-4", "fa-calendar-o", True)}
  {field("montant", "col-md-4", "fa-money", True, "Enveloppe en CDF")}
</div>""", True),
    aside_tips("Une enveloppe par mois et par année", "Le montant plafonne les prestations", "Vérifiez l'année avant enregistrement"),
)

FORMS["prestation/prestation_form.html"] = render_form(
    "prestation/prestation_form.html",
    bc([("Prestations", "prestation:prestation_list")]),
    "prestation:prestation_list",
    "prestation-form",
    "\n".join([
        section("fa-calendar", "Date & agent", "Quand et qui", f"""<div class="row g-3">
  {field("date_prestation", "col-md-4", "fa-calendar", True)}
  {field("personnel", "col-md-8", "fa-user", True)}
</div>"""),
        section("fa-tags", "Barème", "Type et montant", f"""<div class="row g-3">
  {field("categorie", "col-md-4", "fa-tag", True, label="Type prestation")}
  {field("bareme", "col-md-8", "fa-money", True)}
</div>"""),
        section("fa-link", "Compléments", "Horaire lié et observations", f"""<div class="row g-3">
  {field("horaire", "col-md-6", "fa-clock-o", False, "Optionnel")}
  {field("observation", "col-12", "fa-sticky-note")}
</div>""", True),
    ]),
    aside_tips("Le barème dépend du type choisi", "Une enveloppe doit exister pour la date", "L'horaire est facultatif"),
)


# Password change keeps centered layout — not generated here.


def main() -> None:
    for rel, content in FORMS.items():
        if rel in SKIP:
            continue
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {rel}")

    print("Done.")


if __name__ == "__main__":
    main()
