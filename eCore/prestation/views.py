from collections import OrderedDict, defaultdict
from datetime import date, datetime
from io import BytesIO
import os
import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from academics.models import AnneeAcademique, ElementConstitutif
from academics.utils import NO_ACTIVE_ANNEE_ERROR
from cards.models import CardSettings, Personnel
from .forms import (
    BaremePrestationForm,
    CalculPaieForm,
    CloturePaieForm,
    EnveloppeBudgetaireForm,
    FichePrestationJournaliereForm,
    HoraireForm,
    HoraireLigneForm,
    PrestationDepuisHoraireDateForm,
    PrestationDepuisHoraireFiltreForm,
    PrestationDepuisHoraireListeForm,
    PrestationMensuelleListeForm,
    PrestationMensuelleSaisieForm,
    PrestationForm,
    StatistiquesPrestationEnseignementForm,
)
from .models import BaremePrestation, EnveloppeBudgetaire, Horaire, HoraireLigne, PaieMensuelle, Prestation
from .services import (
    cancel_prestation_horaire_ligne,
    cloturer_paie_mensuelle,
    collect_prestation_horaire_rows,
    confirm_prestation_horaire_ligne,
    enregistrer_prestations_mensuelles,
    get_budget_context,
    get_fiches_saisie_horaire,
    get_prestations_mensuelles_queryset,
    get_saisies_prestation_mensuelle,
    get_prestations_mensuelle_groupe,
    modifier_saisie_prestation_mensuelle,
    supprimer_saisie_prestation_mensuelle,
    collect_bulletin_individuel_paie,
    collect_calcul_paie_data,
    get_default_bareme_enseignement,
    get_enveloppe_for_date,
    get_month_label,
    is_paie_mois_cloturee,
)


def _blocage_ajout_prestation_horaire(request, date_prestation, enveloppe_manquante):
    """Message explicite lorsque l'utilisateur ne peut pas cocher une nouvelle ligne."""
    if not request.user.has_perm("prestation.add_prestation"):
        return (
            "Vous n'avez pas la permission d'ajouter une prestation. "
            "Demandez le droit « Ajouter une prestation » à un administrateur."
        )
    if is_paie_mois_cloturee(date_prestation.year, date_prestation.month):
        mois = get_month_label(date_prestation.month)
        return (
            f"La paie de {mois} {date_prestation.year} est clôturée : "
            "aucune nouvelle prestation ne peut être enregistrée pour cette date."
        )
    if enveloppe_manquante:
        mois = get_month_label(date_prestation.month)
        return (
            f"Aucune enveloppe budgétaire pour {mois} {date_prestation.year}. "
            "Créez-la dans le menu Enveloppes budgétaires, puis réessayez."
        )
    if not get_default_bareme_enseignement():
        return (
            "Aucun barème d'enseignement actif n'est configuré. "
            "Créez un barème (catégorie enseignement) avant de valider."
        )
    return ""


def _blocage_annulation_prestation_horaire(request, date_prestation):
    if not (
        request.user.has_perm("prestation.delete_prestation")
        or request.user.has_perm("prestation.change_prestation")
    ):
        return (
            "Vous n'avez pas la permission d'annuler une prestation. "
            "Demandez le droit de modification ou de suppression des prestations."
        )
    if is_paie_mois_cloturee(date_prestation.year, date_prestation.month):
        mois = get_month_label(date_prestation.month)
        return (
            f"La paie de {mois} {date_prestation.year} est clôturée : "
            "vous ne pouvez plus retirer de prestation pour cette date."
        )
    return ""


def _enrich_prestation_horaire_rows(
    rows,
    *,
    date_prestation,
    enveloppe_manquante,
    paie_cloturee,
    can_add,
    can_cancel,
    msg_blocage_ajout,
    msg_blocage_annulation,
):
    mois = get_month_label(date_prestation.month)
    annee = date_prestation.year
    for row in rows:
        if not row["professeur_id"]:
            row["statut_message"] = (
                "Impossible de valider : aucun professeur n'est associé à ce cours. "
                "Assignez un professeur sur la ligne d'horaire concernée."
            )
            row["statut_class"] = "text-danger"
            row["blocage_clic"] = row["statut_message"]
            continue
        if row["validee"]:
            if paie_cloturee:
                row["statut_message"] = (
                    f"Prestation enregistrée — paie de {mois} {annee} clôturée, "
                    "retrait impossible."
                )
                row["statut_class"] = "text-warning"
            elif not can_cancel:
                row["statut_message"] = (
                    f"Prestation enregistrée — {msg_blocage_annulation or 'annulation non autorisée.'}"
                )
                row["statut_class"] = "text-warning"
            else:
                row["statut_message"] = (
                    "Prestation enregistrée — décochez la case pour la retirer."
                )
                row["statut_class"] = "text-success"
            row["blocage_clic"] = msg_blocage_annulation or ""
            continue
        if msg_blocage_ajout:
            row["statut_message"] = msg_blocage_ajout
            row["statut_class"] = "text-warning"
            row["blocage_clic"] = msg_blocage_ajout
            continue
        row["statut_message"] = "Cochez la case « Validé » pour enregistrer cette prestation."
        row["statut_class"] = "text-muted"
        row["blocage_clic"] = ""


def get_horaire_ligne_formset(instance=None, data=None):
    """Formset des lignes : 18 lignes vides à la création, uniquement les existantes en modification."""
    extra = 0 if instance and instance.pk else 18
    FormSet = inlineformset_factory(
        Horaire,
        HoraireLigne,
        form=HoraireLigneForm,
        extra=extra,
        can_delete=True,
        min_num=1,
        validate_min=True,
    )
    if data is not None:
        return FormSet(data, instance=instance, prefix="lignes")
    return FormSet(instance=instance, prefix="lignes")


DAY_ORDER = [
    HoraireLigne.JOUR_LUNDI,
    HoraireLigne.JOUR_MARDI,
    HoraireLigne.JOUR_MERCREDI,
    HoraireLigne.JOUR_JEUDI,
    HoraireLigne.JOUR_VENDREDI,
    HoraireLigne.JOUR_SAMEDI,
]

MONTH_LABELS = {
    "1": "Janvier",
    "2": "Février",
    "3": "Mars",
    "4": "Avril",
    "5": "Mai",
    "6": "Juin",
    "7": "Juillet",
    "8": "Août",
    "9": "Septembre",
    "10": "Octobre",
    "11": "Novembre",
    "12": "Décembre",
}


def _get_calcul_annee():
    return AnneeAcademique.get_active()


def _get_prestation_section(prestation):
    horaire = getattr(prestation, "horaire", None)
    if not horaire or not getattr(horaire, "classe", None):
        return None
    promotion = getattr(horaire.classe, "promotion", None)
    filiere = getattr(promotion, "filiere", None) if promotion else None
    return getattr(filiere, "section", None) if filiere else None


def _section_matches_prestation(prestation, section):
    prestation_section = _get_prestation_section(prestation)
    if prestation_section and prestation_section.pk == section.pk:
        return True
    return False


def _collect_fiche_prestations(section, jour_key, semestre, annee_academique):
    day_labels = {
        HoraireLigne.JOUR_LUNDI: "Lundi",
        HoraireLigne.JOUR_MARDI: "Mardi",
        HoraireLigne.JOUR_MERCREDI: "Mercredi",
        HoraireLigne.JOUR_JEUDI: "Jeudi",
        HoraireLigne.JOUR_VENDREDI: "Vendredi",
        HoraireLigne.JOUR_SAMEDI: "Samedi",
    }
    day_key = jour_key
    if not day_key:
        return {
            "lines": [],
            "day_key": None,
            "day_label": "-",
        }

    lines = HoraireLigne.objects.select_related(
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
        "element_constitutif",
        "element_constitutif__professeur",
        "local",
        "professeur",
        "professeur__category",
    ).filter(
        horaire__active=True,
        horaire__classe__promotion__filiere__section=section,
        horaire__semestre=semestre,
        horaire__annee_academique=annee_academique,
        jour=day_key,
    ).order_by(
        "horaire__classe__promotion__code",
        "horaire__classe__code",
        "heure_debut",
        "ordre",
    )

    rows = []
    for index, line in enumerate(lines, start=1):
        personnel = line.professeur_affichage
        rows.append({
            "numero": index,
            "nom_prenom": f"{personnel.last_name} {personnel.first_name}".strip() if personnel else "-",
            "categorie": personnel.category.name if personnel and personnel.category else "-",
            "ue": f"{line.code_affichage}" if line.code_affichage else "-",
            "heure_debut": line.heure_debut.strftime("%Hh%M"),
            "heure_fin": line.heure_fin.strftime("%Hh%M"),
            "classe": line.horaire.classe.nom if line.horaire and line.horaire.classe else "-",
            "local": line.local.nom if line.local else "-",
            "signature": "",
            "line": line,
        })

    return {
        "lines": rows,
        "day_key": day_key,
        "day_label": day_labels.get(day_key, "-"),
    }


def _format_statistiques_enseignement_range(date_debut, date_fin):
    if date_debut and date_fin:
        return f"du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    if date_debut:
        return f"à partir du {date_debut.strftime('%d/%m/%Y')}"
    if date_fin:
        return f"jusqu'au {date_fin.strftime('%d/%m/%Y')}"
    return "sur la période sélectionnée"


def _get_statistiques_enseignement_ue_code(prestation):
    horaire = prestation.horaire
    if not horaire:
        return prestation.bareme.intitule if prestation.bareme else "-"

    lignes = getattr(horaire, "lignes", None)
    if lignes is not None:
        qs = horaire.lignes.all()
        if prestation.personnel_id:
            qs = qs.filter(professeur_id=prestation.personnel_id)
        ligne = qs.order_by("ordre", "heure_debut").first()
        if ligne:
            code = (ligne.code_affichage or "").strip()
            if code and code != "-":
                return code

    ligne = horaire.lignes.order_by("ordre", "heure_debut").first()
    if ligne:
        code = (ligne.code_affichage or "").strip()
        if code and code != "-":
            return code

    return prestation.bareme.intitule if prestation.bareme else "-"


def _collect_statistiques_prestations_enseignement(section, annee_academique, semestre, date_debut, date_fin):
    prestations = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
    ).prefetch_related(
        "horaire__lignes",
        "horaire__lignes__element_constitutif",
    ).filter(
        bareme__categorie=BaremePrestation.CATEGORIE_ENSEIGNEMENT,
        date_prestation__range=(date_debut, date_fin),
        horaire__annee_academique=annee_academique,
        horaire__semestre=semestre,
        horaire__classe__promotion__filiere__section=section,
    ).order_by(
        "personnel__last_name",
        "personnel__first_name",
        "date_prestation",
    )

    grouped = OrderedDict()
    for prestation in prestations:
        personnel = prestation.personnel
        if not personnel:
            continue
        ue_label = _get_statistiques_enseignement_ue_code(prestation)
        ue_key = re.sub(r"\s+", " ", ue_label).strip().lower()
        if not ue_key:
            ue_key = f"horaire:{prestation.horaire_id or 'none'}"
        key = (personnel.pk, ue_key)
        if key not in grouped:
            grouped[key] = {
                "personnel": personnel,
                "ue": ue_label or "-",
                "ue_key": ue_key,
                "nombre_prestations": 0,
            }
        grouped[key]["nombre_prestations"] += 1

    rows = []
    for index, item in enumerate(sorted(
        grouped.values(),
        key=lambda row: (
            (row["personnel"].last_name or "").lower(),
            (row["personnel"].first_name or "").lower(),
            (row["ue"] or "").lower(),
        ),
    ), start=1):
        personnel = item["personnel"]
        rows.append({
            "numero": index,
            "nom": personnel.last_name or "",
            "prenom": personnel.first_name or "",
            "nom_prenom": f"{personnel.last_name} {personnel.first_name}".strip(),
            "ue": item["ue"],
            "nombre_prestations": item["nombre_prestations"],
        })

    return {
        "rows": rows,
        "total_lignes": len(prestations),
        "total_lignes_stats": sum(item["nombre_prestations"] for item in rows),
    }


def _collect_paie_data(mois, section, annee):
    return collect_calcul_paie_data(mois, section, annee)


def _collect_individual_bulletin(personnel, mois, section, annee):
    return collect_bulletin_individuel_paie(personnel, mois, section, annee)


def _build_header_table(body_style, direction, ecole, systeme_affichage, right_title, right_value):
    logo = _logo_flowable(_asset_path("static", "images", "logoeifi.png"), width_mm=20)
    header_table = Table([[
        logo if logo else Paragraph("EIFI", ParagraphStyle("LogoFallback", parent=body_style, fontName="Helvetica-Bold", fontSize=16, textColor=colors.white)),
        Paragraph(f"<b>{direction}</b><br/>{ecole}<br/>{systeme_affichage}", ParagraphStyle(
            "HeaderTitle",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=11.2,
            leading=13,
            textColor=colors.white,
        )),
        Paragraph(f"<b>{right_title}</b><br/>{right_value}", ParagraphStyle(
            "HeaderRight",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        )),
    ]], colWidths=[24 * mm, 112 * mm, 40 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0f172a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#334155")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return header_table


def _build_signature_footer(body_style):
    settings_row = CardSettings.objects.first()
    chief_name = settings_row.training_division_chief_name if settings_row else ""
    right_footer_style = ParagraphStyle(
        "RightFooter",
        parent=body_style,
        alignment=TA_LEFT,
        leading=9,
        spaceBefore=0,
        spaceAfter=0,
    )
    footer_block = [
        Paragraph(f"Fait à Kinshasa le {date.today().strftime('%d/%m/%Y')}", right_footer_style),
        Spacer(1, 0.8 * mm),
        Paragraph("<u><b>LE CHEF DE DIVISION FORMATION</b></u>", right_footer_style),
    ]
    if chief_name:
        footer_block.append(Spacer(1, 0.8 * mm))
        footer_block.append(Paragraph(chief_name, right_footer_style))
    footer_table = Table([["", footer_block]], colWidths=[108 * mm, 72 * mm])
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return footer_table


def _group_lines_by_day(lines):
    grouped = OrderedDict((day, []) for day in DAY_ORDER)
    for line in lines:
        grouped.setdefault(line.jour, []).append(line)
    return grouped


def _format_time_range(line):
    return f"{line.heure_debut.strftime('%Hh%M')}-{line.heure_fin.strftime('%Hh%M')}"


def _format_ue_cell_html(line):
    code = line.code_affichage
    parts = [f'<b><font color="#0284c7">{code}</font></b>']
    if line.intitule_affichage:
        parts.append(f'<font color="#475569">{line.intitule_affichage}</font>')
    return "<br/>".join(parts)


def _unique_legend_items(lines):
    seen = set()
    items = []
    for line in lines:
        code = line.code_affichage
        key = (code, line.titulaire_affichage)
        if key in seen:
            continue
        seen.add(key)
        title = line.intitule_affichage or code
        if line.intitule_affichage and line.intitule_affichage != code:
            title = f"{code} — {line.intitule_affichage}"
        items.append((title, line.titulaire_affichage))
    return items


def _build_ec_professeur_map():
    mapping = {}
    for ec in ElementConstitutif.objects.select_related("professeur").filter(active=True):
        if ec.professeur_id:
            professeur = ec.professeur
            mapping[str(ec.pk)] = {
                "id": professeur.pk,
                "label": f"{professeur.last_name} {professeur.first_name}".strip(),
            }
    return mapping


def _asset_path(*parts):
    return os.path.join(str(settings.BASE_DIR), *parts)


def _logo_flowable(path, width_mm=18):
    if not path or not os.path.exists(path):
        return None
    img = RLImage(path)
    img.drawHeight = width_mm * mm * img.drawHeight / img.drawWidth
    img.drawWidth = width_mm * mm
    return img


def _draw_page_number(c, doc):
    page_number = c.getPageNumber()
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawRightString(doc.pagesize[0] - 15 * mm, 10 * mm, f"Page {page_number}")
    c.restoreState()


@login_required
def bareme_list(request):
    baremes = BaremePrestation.objects.all().order_by("categorie", "ordre", "intitule")
    return render(request, "prestation/bareme_list.html", {"baremes": baremes})


@login_required
def bareme_create(request):
    if request.method == "POST":
        form = BaremePrestationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Barème enregistré avec succès.")
            return redirect("prestation:bareme_list")
    else:
        form = BaremePrestationForm()
    return render(request, "prestation/bareme_form.html", {"form": form, "title": "Nouveau barème"})


@login_required
def bareme_update(request, pk):
    bareme = get_object_or_404(BaremePrestation, pk=pk)
    if request.method == "POST":
        form = BaremePrestationForm(request.POST, instance=bareme)
        if form.is_valid():
            form.save()
            messages.success(request, "Barème modifié avec succès.")
            return redirect("prestation:bareme_list")
    else:
        form = BaremePrestationForm(instance=bareme)
    return render(request, "prestation/bareme_form.html", {"form": form, "title": "Modifier le barème", "bareme": bareme})


@login_required
def bareme_delete(request, pk):
    bareme = get_object_or_404(BaremePrestation, pk=pk)
    if request.method == "POST":
        bareme.delete()
        messages.success(request, "Barème supprimé avec succès.")
        return redirect("prestation:bareme_list")
    return render(request, "prestation/bareme_confirm_delete.html", {"bareme": bareme})


@login_required
def enveloppe_list(request):
    enveloppes = []
    for enveloppe in EnveloppeBudgetaire.objects.select_related("paie_validee").all():
        budget = get_budget_context(enveloppe.annee, enveloppe.mois)
        enveloppe.total_engage = budget["total_engage"]
        enveloppe.solde_disponible = budget["solde_disponible"]
        enveloppe.depasse = budget["depasse"]
        enveloppes.append(enveloppe)
    return render(request, "prestation/enveloppe_list.html", {"enveloppes": enveloppes})


@login_required
def enveloppe_create(request):
    if request.method == "POST":
        form = EnveloppeBudgetaireForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Enveloppe budgétaire enregistrée avec succès.")
            return redirect("prestation:enveloppe_list")
    else:
        form = EnveloppeBudgetaireForm()
    return render(request, "prestation/enveloppe_form.html", {"form": form, "title": "Nouvelle enveloppe budgétaire"})


@login_required
def enveloppe_update(request, pk):
    enveloppe = get_object_or_404(EnveloppeBudgetaire, pk=pk)
    if PaieMensuelle.objects.filter(enveloppe=enveloppe).exists():
        messages.error(request, "Cette enveloppe est liée à une paie déjà validée et ne peut plus être modifiée.")
        return redirect("prestation:enveloppe_list")
    if request.method == "POST":
        form = EnveloppeBudgetaireForm(request.POST, instance=enveloppe)
        if form.is_valid():
            form.save()
            messages.success(request, "Enveloppe budgétaire modifiée avec succès.")
            return redirect("prestation:enveloppe_list")
    else:
        form = EnveloppeBudgetaireForm(instance=enveloppe)
    return render(
        request,
        "prestation/enveloppe_form.html",
        {"form": form, "title": "Modifier l'enveloppe budgétaire", "enveloppe": enveloppe},
    )


@login_required
def enveloppe_delete(request, pk):
    enveloppe = get_object_or_404(EnveloppeBudgetaire, pk=pk)
    if PaieMensuelle.objects.filter(enveloppe=enveloppe).exists():
        messages.error(request, "Cette enveloppe est liée à une paie validée et ne peut pas être supprimée.")
        return redirect("prestation:enveloppe_list")
    if request.method == "POST":
        enveloppe.delete()
        messages.success(request, "Enveloppe budgétaire supprimée avec succès.")
        return redirect("prestation:enveloppe_list")
    return render(request, "prestation/enveloppe_confirm_delete.html", {"enveloppe": enveloppe})


@login_required
def cloture_paie_mensuelle(request):
    resume = None
    form = CloturePaieForm(request.GET or None)

    if request.method == "POST":
        form = CloturePaieForm(request.POST)
        if form.is_valid() and "cloturer" in request.POST:
            annee = int(form.cleaned_data["annee"])
            mois = int(form.cleaned_data["mois"])
            try:
                cloturer_paie_mensuelle(annee, mois, request.user)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"La paie de {get_month_label(mois)} {annee} a été clôturée avec succès.",
                )
            return redirect(f"{reverse('prestation:cloture_paie_mensuelle')}?annee={annee}&mois={mois}")

    if form.is_valid():
        annee = int(form.cleaned_data["annee"])
        mois = int(form.cleaned_data["mois"])
        budget = get_budget_context(annee, mois)
        resume = {
            "annee": annee,
            "mois": mois,
            "mois_label": budget["mois_label"],
            "budget": budget,
        }

    return render(request, "prestation/cloture_paie_mensuelle.html", {
        "form": form,
        "resume": resume,
    })


@login_required
def prestation_list(request):
    prestations = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
    ).all()
    return render(request, "prestation/prestation_list.html", {"prestations": prestations})


@login_required
def prestation_create(request):
    if request.method == "POST":
        form = PrestationForm(request.POST)
        if form.is_valid():
            prestation = form.save(commit=False)
            prestation.save()
            messages.success(request, "Prestation enregistrée avec succès.")
            return redirect("prestation:prestation_list")
    else:
        form = PrestationForm()
    return render(request, "prestation/prestation_form.html", {"form": form, "title": "Nouvelle prestation"})


@login_required
def prestation_update(request, pk):
    prestation = get_object_or_404(Prestation, pk=pk)
    if not get_enveloppe_for_date(prestation.date_prestation):
        messages.error(request, "Aucune enveloppe budgétaire n'a été trouvée.")
        return redirect("prestation:prestation_list")
    if request.method == "POST":
        form = PrestationForm(request.POST, instance=prestation)
        if form.is_valid():
            prestation = form.save(commit=False)
            prestation.save()
            messages.success(request, "Prestation modifiée avec succès.")
            return redirect("prestation:prestation_list")
    else:
        form = PrestationForm(instance=prestation)
    return render(request, "prestation/prestation_form.html", {"form": form, "title": "Modifier la prestation", "prestation": prestation})


@login_required
def prestation_delete(request, pk):
    prestation = get_object_or_404(Prestation, pk=pk)
    if not get_enveloppe_for_date(prestation.date_prestation):
        messages.error(request, "Aucune enveloppe budgétaire n'a été trouvée.")
        return redirect("prestation:prestation_list")
    if request.method == "POST":
        prestation.delete()
        messages.success(request, "Prestation supprimée avec succès.")
        return redirect("prestation:prestation_list")
    return render(request, "prestation/prestation_confirm_delete.html", {"prestation": prestation})


@login_required
def api_baremes_by_categorie(request):
    categorie = request.GET.get("categorie")
    baremes = BaremePrestation.objects.filter(active=True)
    if categorie:
        baremes = baremes.filter(categorie=categorie)
    data = [
        {
            "id": bareme.id,
            "label": bareme.intitule,
            "montant": str(bareme.montant),
            "categorie": bareme.categorie,
        }
        for bareme in baremes.order_by("ordre", "intitule")
    ]
    return JsonResponse({"results": data})


@login_required
def calcul_paie(request):
    calculation = None
    resultats = []
    total_general = 0
    total_prestations = 0
    total_personnels = 0
    annee_academique = _get_calcul_annee()

    budget = None
    if request.method == "POST":
        form = CalculPaieForm(request.POST)
        if form.is_valid():
            annee = int(form.cleaned_data["annee"])
            mois = int(form.cleaned_data["mois"])
            section = form.cleaned_data["section"]
            budget = get_budget_context(annee, mois)
            if budget["deja_cloturee"]:
                messages.error(
                    request,
                    f"La paie de {get_month_label(mois)} {annee} est clôturée. "
                    "Le calcul n'est plus autorisé pour ce mois.",
                )
            else:
                paie_data = _collect_paie_data(mois, section, annee)
                resultats = paie_data["resultats"]
                total_general = paie_data["total_general"]
                total_prestations = paie_data["total_prestations"]
                total_personnels = paie_data["total_personnels"]
                if paie_data["fallback_used"]:
                    messages.warning(
                        request,
                        "Aucune prestation n'est rattachée à cette section dans les données. Le calcul affiche donc toutes les prestations du mois sélectionné.",
                    )
                elif not paie_data["prestations"]:
                    messages.info(request, "Aucune prestation trouvée pour ce mois et cette section.")
                if budget["depasse"]:
                    messages.error(request, budget["message"])
                for alerte in paie_data.get("alertes_globales", [])[:5]:
                    messages.warning(request, alerte)
                if len(paie_data.get("alertes_globales", [])) > 5:
                    messages.warning(
                        request,
                        f"{len(paie_data['alertes_globales']) - 5} autre(s) alerte(s) barème initial — voir le détail par personnel.",
                    )
                calculation = {
                    "mois": MONTH_LABELS.get(str(mois), str(mois)),
                    "annee": annee,
                    "annee_academique": annee_academique,
                    "section": section,
                    "prestations": paie_data["prestations"],
                    "prestations_trouvees": paie_data["total_prestations"],
                    "totals_by_bareme": paie_data["totals_by_bareme"],
                    "total_horaire_global": paie_data["total_horaire_global"],
                    "total_mensuelles_global": paie_data["total_mensuelles_global"],
                }
    else:
        form = CalculPaieForm()

    return render(request, "prestation/calcul_paie.html", {
        "form": form,
        "calculation": calculation,
        "annee_academique": annee_academique,
        "budget": budget,
        "resultats": resultats,
        "total_general": total_general,
        "total_prestations": total_prestations,
        "total_personnels": total_personnels,
        "total_horaire_global": calculation["total_horaire_global"] if calculation else 0,
        "total_mensuelles_global": calculation["total_mensuelles_global"] if calculation else 0,
    })


@login_required
def bulletin_paie(request):
    annee_academique = _get_calcul_annee()
    form = CalculPaieForm(request.GET or None)
    bulletin = None
    download_query = ""

    budget = None
    if form.is_valid():
        annee = int(form.cleaned_data["annee"])
        mois = int(form.cleaned_data["mois"])
        section = form.cleaned_data["section"]
        paie_data = _collect_paie_data(mois, section, annee)
        budget = get_budget_context(annee, mois)
        if paie_data["fallback_used"]:
            messages.warning(
                request,
                "Aucune prestation n'est rattachée à cette section dans les données. Le bulletin affiche donc toutes les prestations du mois sélectionné.",
            )
        elif not paie_data["prestations"]:
            messages.info(request, "Aucune prestation trouvée pour ce mois et cette section.")
        if budget["depasse"]:
            messages.error(request, budget["message"])

        section_label = section.nom or section.code or "SECTION"
        bulletin = {
            "mois": MONTH_LABELS.get(str(mois), str(mois)),
            "annee": annee,
            "mois_numero": mois,
            "section": section,
            "section_label": section_label,
            "annee_academique": annee_academique,
            "resultats": paie_data["resultats"],
            "total_general": paie_data["total_general"],
            "total_prestations": paie_data["total_prestations"],
            "total_personnels": paie_data["total_personnels"],
        }
        download_query = f"annee={annee}&mois={mois}&section={section.pk}"

    return render(request, "prestation/bulletin_paie.html", {
        "form": form,
        "bulletin": bulletin,
        "annee_academique": annee_academique,
        "budget": budget,
        "download_query": download_query,
    })


def _build_bulletin_pdf(bulletin):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BulletinTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.2,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "CenterSmall",
        parent=body_style,
        alignment=TA_CENTER,
    )

    story = []
    bulletin_title = bulletin.get("titre") or (
        f"BULLETIN DE PAIE - {bulletin['mois']} {bulletin['annee_academique'].code if bulletin.get('annee_academique') else ''}"
    )
    direction = "DIRECTION DES SYSTEMES D'INFORMATION"
    ecole = "ECOLE INFORMATIQUE DES FINANCES"
    systeme_affichage = f"SYSTÈME LMD/{bulletin['section_label']}"
    year_text = bulletin["annee_academique"].code if bulletin.get("annee_academique") else "AUTOMATIQUE"
    story.append(_build_header_table(body_style, direction, ecole, systeme_affichage, "ANNEE ACADEMIQUE", year_text))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"<u><b>{bulletin_title}</b></u>",
        title_style,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Section : <b>{bulletin['section_label']}</b>",
        ParagraphStyle(
            "BulletinMeta",
            parent=body_style,
            fontSize=8.6,
            leading=10.2,
            textColor=colors.HexColor("#334155"),
        ),
    ))
    story.append(Spacer(1, 3 * mm))

    for index, item in enumerate(bulletin["resultats"]):
        if index > 0:
            story.append(PageBreak())
            story.append(_build_header_table(body_style, direction, ecole, systeme_affichage, "ANNEE ACADEMIQUE", year_text))
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(
                f"<u><b>{bulletin_title}</b></u>",
                title_style,
            ))
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(
                f"Section : <b>{bulletin['section_label']}</b>",
                ParagraphStyle(
                    "BulletinMetaRepeat",
                    parent=body_style,
                    fontSize=8.6,
                    leading=10.2,
                    textColor=colors.HexColor("#334155"),
                ),
            ))
            story.append(Spacer(1, 3 * mm))

        info_table = Table([[
            Paragraph("<b>Personnel</b>", body_style),
            Paragraph(item["personnel"].__str__(), body_style),
            Paragraph("<b>Prestations horaire</b>", body_style),
            Paragraph(
                f"{item.get('nb_horaire', 0)} — {int(item.get('total_horaire', 0)):,} CDF".replace(",", " "),
                body_style,
            ),
        ], [
            Paragraph("<b>Prestations mensuelles</b>", body_style),
            Paragraph(
                f"{item.get('nb_mensuelle', 0)} — {int(item.get('total_mensuelles', 0)):,} CDF".replace(",", " "),
                body_style,
            ),
            Paragraph("<b>Total à payer</b>", body_style),
            Paragraph(f"{int(item['total']):,} CDF".replace(",", " "), body_style),
        ], [
            Paragraph("<b>Mois</b>", body_style),
            Paragraph(bulletin["mois"], body_style),
            Paragraph("<b>Nombre de lignes</b>", body_style),
            Paragraph(str(len(item["prestations"])), body_style),
        ]], colWidths=[35 * mm, 65 * mm, 40 * mm, 42 * mm])
        info_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2ff")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 4 * mm))

        table_data = [[
            Paragraph("<b>Date</b>", center_style),
            Paragraph("<b>Source</b>", center_style),
            Paragraph("<b>Barème / calcul</b>", center_style),
            Paragraph("<b>Montant</b>", center_style),
        ]]
        for ligne in item["prestations"]:
            calcul_label = ligne.get("formule", "")
            bareme_text = ligne.get("bareme_label", "-")
            if calcul_label:
                bareme_text = f"{bareme_text} ({calcul_label})"
            table_data.append([
                Paragraph(ligne["date_prestation"].strftime("%d/%m/%Y"), body_style),
                Paragraph(ligne.get("source_label", ""), body_style),
                Paragraph(bareme_text, body_style),
                Paragraph(f"{int(ligne['montant']):,} CDF".replace(",", " "), body_style),
            ])
        table_data.append([
            Paragraph("<b>Total</b>", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph(f"<b>{int(item['total']):,} CDF</b>".replace(",", " "), body_style),
        ])
        detail_table = Table(table_data, colWidths=[30 * mm, 70 * mm, 55 * mm, 32 * mm], repeatRows=1)
        detail_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0f2fe")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 4 * mm))
        story.append(_build_signature_footer(body_style))

    if not bulletin["resultats"]:
        story.append(Paragraph(
            "Aucune prestation trouvée pour générer un bulletin de paie.",
            body_style,
        ))

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def bulletin_paie_pdf(request):
    form = CalculPaieForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un mois et une section pour générer le bulletin de paie.")
        return redirect("prestation:bulletin_paie")

    annee = int(form.cleaned_data["annee"])
    mois = int(form.cleaned_data["mois"])
    section = form.cleaned_data["section"]
    paie_data = _collect_paie_data(mois, section, annee)
    bulletin = {
        "mois": MONTH_LABELS.get(str(mois), str(mois)),
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "annee_academique": _get_calcul_annee(),
        "resultats": paie_data["resultats"],
    }
    pdf_buffer = _build_bulletin_pdf(bulletin)
    filename = f"bulletin_paie_{annee}_{mois}_{section.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def bulletin_paie_individuel_pdf(request, personnel_id):
    form = CalculPaieForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un mois et une section pour générer le bulletin individuel.")
        return redirect("prestation:etat_paie_mensuel")

    annee = int(form.cleaned_data["annee"])
    mois = int(form.cleaned_data["mois"])
    section = form.cleaned_data["section"]
    personnel = get_object_or_404(Personnel, pk=personnel_id)
    bulletin_item = _collect_individual_bulletin(personnel, mois, section, annee)
    bulletin = {
        "mois": MONTH_LABELS.get(str(mois), str(mois)),
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "annee_academique": _get_calcul_annee(),
        "resultats": [{
            "personnel": personnel,
            "prestations": bulletin_item["prestations"],
            "total": bulletin_item["total_general"],
            "total_horaire": bulletin_item.get("total_horaire", 0),
            "total_mensuelles": bulletin_item.get("total_mensuelles", 0),
            "nb_horaire": sum(1 for l in bulletin_item["prestations"] if l.get("source") == "horaire"),
            "nb_mensuelle": sum(1 for l in bulletin_item["prestations"] if l.get("source") == "mensuelle"),
        }],
        "titre": f"BULLETIN DE PAIE INDIVIDUEL - {personnel.first_name} {personnel.last_name}",
    }
    pdf_buffer = _build_bulletin_pdf(bulletin)
    filename = f"bulletin_paie_{mois}_{section.pk}_{personnel.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_fiche_prestations_journaliere_pdf(fiche):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=5 * mm,
        leftMargin=5 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FicheJourTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.2,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "FicheJourBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=8.6,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "FicheJourCenter",
        parent=body_style,
        alignment=TA_CENTER,
    )

    direction = "DIRECTION DES SYSTEMES D'INFORMATION"
    ecole = "ECOLE INFORMATIQUE DES FINANCES"
    section_label = fiche["section_label"]
    year_text = fiche["annee_academique"].code if fiche.get("annee_academique") else "AUTOMATIQUE"
    story = [
        _build_header_table(body_style, direction, ecole, f"SYSTÈME LMD/{section_label}", "ANNEE ACADEMIQUE", year_text),
        Spacer(1, 4 * mm),
        Paragraph(
            f"<u><b>FICHE DES PRESTATIONS JOURNALIÈRES - {fiche['date_label']}</b></u>",
            title_style,
        ),
        Spacer(1, 1 * mm),
        Paragraph(
            f"Générée le <b>{fiche.get('generated_label', date.today().strftime('%d/%m/%Y'))}</b>",
            ParagraphStyle(
                "FicheJourGenerated",
                parent=body_style,
                fontSize=8,
                leading=9,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#64748b"),
            ),
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Section : <b>{section_label}</b>",
            ParagraphStyle(
                "FicheJourMeta",
                parent=body_style,
                fontSize=8.4,
                leading=10,
                textColor=colors.HexColor("#334155"),
            ),
        ),
        Spacer(1, 3 * mm),
    ]

    table_data = [[
        Paragraph("<b>N°</b>", center_style),
        Paragraph("<b>NOM &amp; PRÉNOM</b>", center_style),
        Paragraph("<b>CATÉGORIE</b>", center_style),
        Paragraph("<b>UE</b>", center_style),
        Paragraph("<b>HEURE DÉBUT</b>", center_style),
        Paragraph("<b>HEURE FIN</b>", center_style),
        Paragraph("<b>CLASSE</b>", center_style),
        Paragraph("<b>LOCAL</b>", center_style),
        Paragraph("<b>SIGNATURE</b>", center_style),
    ]]

    for row in fiche["rows"]:
        table_data.append([
            Paragraph(str(row["numero"]), center_style),
            Paragraph(row["nom_prenom"], body_style),
            Paragraph(row["categorie"], body_style),
            Paragraph(row["ue"], body_style),
            Paragraph(row["heure_debut"], center_style),
            Paragraph(row["heure_fin"], center_style),
            Paragraph(row["classe"], body_style),
            Paragraph(row["local"], body_style),
            Paragraph(" ", body_style),
        ])

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", center_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
        ])

    table = Table(
        table_data,
        colWidths=[
            10 * mm,
            60 * mm,
            24 * mm,
            22 * mm,
            18 * mm,
            18 * mm,
            25 * mm,
            20 * mm,
            90 * mm,
        ],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 1), (5, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def prestation_mensuelle_list(request):
    if request.GET.get("detail") == "1":
        params = {
            key: request.GET[key]
            for key in ("mois", "annee", "numero_fiche")
            if request.GET.get(key)
        }
        if params:
            return redirect(f"{reverse('prestation:prestation_mensuelle_list')}?{urlencode(params)}")
        return redirect("prestation:prestation_mensuelle_list")

    if request.GET:
        filtre_form = PrestationMensuelleListeForm(request.GET)
    else:
        today = date.today()
        filtre_form = PrestationMensuelleListeForm(
            initial={"mois": str(today.month), "annee": str(today.year)},
        )

    saisies = []

    if filtre_form.is_valid():
        mois = filtre_form.cleaned_data.get("mois")
        annee = filtre_form.cleaned_data.get("annee")
        numero_fiche = filtre_form.cleaned_data.get("numero_fiche")
        saisies = get_saisies_prestation_mensuelle(
            annee=int(annee) if annee else None,
            mois=int(mois) if mois else None,
            numero_fiche=numero_fiche,
        )
    elif not request.GET:
        today = date.today()
        saisies = get_saisies_prestation_mensuelle(
            annee=today.year,
            mois=today.month,
        )

    total_saisies = len(saisies)
    total_lignes = sum(s["nb_lignes"] for s in saisies)
    total_montant = sum(s["total_montant"] for s in saisies)

    return render(
        request,
        "prestation/prestation_mensuelle_list.html",
        {
            "filtre_form": filtre_form,
            "saisies": saisies,
            "total_montant": total_montant,
            "total_lignes": total_lignes,
            "total_saisies": total_saisies,
        },
    )


@login_required
def prestation_mensuelle_saisie(request):
    form = PrestationMensuelleSaisieForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            quantite = enregistrer_prestations_mensuelles(
                annee=form.cleaned_data["annee"],
                mois=form.cleaned_data["mois"],
                numero_fiche=form.cleaned_data["numero_fiche"],
                personnel=form.cleaned_data["personnel"],
                bareme=form.cleaned_data["bareme"],
                quantite=form.cleaned_data["quantite"],
            )
            messages.success(
                request,
                f"{quantite} prestation(s) enregistrée(s) avec succès.",
            )
            params = urlencode({
                "mois": form.cleaned_data["mois"],
                "annee": form.cleaned_data["annee"],
                "numero_fiche": form.cleaned_data["numero_fiche"],
            })
            return redirect(f"{reverse('prestation:prestation_mensuelle_list')}?{params}")
        except ValueError as exc:
            messages.error(request, str(exc))

    return render(
        request,
        "prestation/prestation_mensuelle_saisie.html",
        {"form": form},
    )


@login_required
def prestation_mensuelle_modifier(request):
    if not (
        request.user.has_perm("prestation.change_prestation")
        or request.user.has_perm("prestation.add_prestation")
    ):
        messages.error(request, "Vous n'avez pas la permission de modifier cette saisie.")
        return redirect("prestation:prestation_mensuelle_list")

    keys = _parse_saisie_mensuelle_keys(request.GET if request.method == "GET" else request.POST)
    if not keys:
        messages.error(request, "Paramètres de saisie incomplets.")
        return redirect("prestation:prestation_mensuelle_list")

    groupe = get_prestations_mensuelle_groupe(**keys)
    if not groupe.exists():
        messages.error(request, "Saisie mensuelle introuvable.")
        return redirect("prestation:prestation_mensuelle_list")

    first = groupe.select_related("personnel", "bareme").first()

    if request.method == "POST":
        form = PrestationMensuelleSaisieForm(request.POST)
        if form.is_valid():
            try:
                orig_keys = _parse_orig_saisie_mensuelle_keys(request.POST)
                if not orig_keys:
                    raise ValueError("Référence de la saisie d'origine manquante.")
                quantite = modifier_saisie_prestation_mensuelle(
                    orig_annee=orig_keys["annee"],
                    orig_mois=orig_keys["mois"],
                    orig_numero_fiche=orig_keys["numero_fiche"],
                    orig_personnel_id=orig_keys["personnel_id"],
                    orig_bareme_id=orig_keys["bareme_id"],
                    annee=form.cleaned_data["annee"],
                    mois=int(form.cleaned_data["mois"]),
                    numero_fiche=form.cleaned_data["numero_fiche"],
                    personnel=form.cleaned_data["personnel"],
                    bareme=form.cleaned_data["bareme"],
                    quantite=form.cleaned_data["quantite"],
                )
                messages.success(
                    request,
                    f"Saisie modifiée : {quantite} prestation(s) enregistrée(s).",
                )
                params = urlencode({
                    "mois": form.cleaned_data["mois"],
                    "annee": form.cleaned_data["annee"],
                    "numero_fiche": form.cleaned_data["numero_fiche"],
                })
                return redirect(f"{reverse('prestation:prestation_mensuelle_list')}?{params}")
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = PrestationMensuelleSaisieForm(
            initial={
                "mois": str(keys["mois"]),
                "annee": keys["annee"],
                "numero_fiche": keys["numero_fiche"],
                "personnel": keys["personnel_id"],
                "bareme": keys["bareme_id"],
                "quantite": groupe.count(),
            },
        )

    mois_labels = dict(PrestationMensuelleSaisieForm.base_fields["mois"].choices)
    saisie_resume = {
        "periode": f"{mois_labels.get(str(keys['mois']), keys['mois'])} {keys['annee']}",
        "numero_fiche": keys["numero_fiche"],
        "personnel_label": str(first.personnel) if first else "-",
        "bareme_label": str(first.bareme) if first else "-",
        "nb_lignes": groupe.count(),
    }

    return render(
        request,
        "prestation/prestation_mensuelle_modifier.html",
        {
            "form": form,
            "keys": keys,
            "saisie_resume": saisie_resume,
        },
    )


@login_required
def prestation_mensuelle_supprimer(request):
    keys = _parse_saisie_mensuelle_keys(request.GET if request.method == "GET" else request.POST)
    if not keys:
        messages.error(request, "Paramètres de saisie incomplets.")
        return redirect("prestation:prestation_mensuelle_list")

    groupe = get_prestations_mensuelle_groupe(**keys).select_related("personnel", "bareme")
    if not groupe.exists():
        messages.error(request, "Saisie mensuelle introuvable.")
        return redirect("prestation:prestation_mensuelle_list")

    if request.method == "POST":
        if not (
            request.user.has_perm("prestation.delete_prestation")
            or request.user.has_perm("prestation.change_prestation")
        ):
            messages.error(request, "Vous n'avez pas la permission de supprimer cette saisie.")
            return redirect("prestation:prestation_mensuelle_list")
        try:
            nb = supprimer_saisie_prestation_mensuelle(**keys)
            messages.success(request, f"Saisie supprimée ({nb} ligne(s) retirée(s)).")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(f"{reverse('prestation:prestation_mensuelle_list')}?{_saisie_mensuelle_list_redirect_params(keys)}")

    first = groupe.first()
    mois_labels = dict(PrestationMensuelleSaisieForm.base_fields["mois"].choices)
    saisie_resume = {
        "periode": f"{mois_labels.get(str(keys['mois']), keys['mois'])} {keys['annee']}",
        "numero_fiche": keys["numero_fiche"],
        "personnel_label": str(first.personnel),
        "bareme_label": str(first.bareme),
        "nb_lignes": groupe.count(),
        "total_montant": groupe.aggregate(total=Sum("montant"))["total"] or 0,
    }

    return render(
        request,
        "prestation/prestation_mensuelle_confirm_delete.html",
        {"keys": keys, "saisie_resume": saisie_resume},
    )


def _parse_saisie_mensuelle_keys(data):
    """Extrait les clés d'une saisie mensuelle depuis GET ou POST."""
    mois = data.get("mois")
    annee = data.get("annee")
    numero_fiche = (data.get("numero_fiche") or "").strip()
    personnel = data.get("personnel")
    bareme = data.get("bareme")
    if not all([mois, annee, numero_fiche, personnel, bareme]):
        return None
    try:
        return {
            "mois": int(mois),
            "annee": int(annee),
            "numero_fiche": numero_fiche,
            "personnel_id": int(personnel),
            "bareme_id": int(bareme),
        }
    except (TypeError, ValueError):
        return None


def _parse_orig_saisie_mensuelle_keys(data):
    """Clés de la saisie d'origine (champs cachés lors d'une modification)."""
    mois = data.get("orig_mois")
    annee = data.get("orig_annee")
    numero_fiche = (data.get("orig_numero_fiche") or "").strip()
    personnel = data.get("orig_personnel")
    bareme = data.get("orig_bareme")
    if not all([mois, annee, numero_fiche, personnel, bareme]):
        return None
    try:
        return {
            "mois": int(mois),
            "annee": int(annee),
            "numero_fiche": numero_fiche,
            "personnel_id": int(personnel),
            "bareme_id": int(bareme),
        }
    except (TypeError, ValueError):
        return None


def _saisie_mensuelle_list_redirect_params(keys):
    return urlencode({
        "mois": keys["mois"],
        "annee": keys["annee"],
        "numero_fiche": keys["numero_fiche"],
    })


def _parse_date_prestation_param(raw_value):
    if not raw_value:
        return date.today()
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


@login_required
def prestation_depuis_horaire_list(request):
    if request.GET:
        filtre_form = PrestationDepuisHoraireListeForm(request.GET)
    else:
        today = date.today()
        filtre_form = PrestationDepuisHoraireListeForm(
            initial={"mois": str(today.month), "annee": str(today.year)},
        )

    fiches = get_fiches_saisie_horaire()
    if filtre_form.is_valid():
        mois = filtre_form.cleaned_data.get("mois")
        annee = filtre_form.cleaned_data.get("annee")
        fiches = get_fiches_saisie_horaire(
            numero_fiche=filtre_form.cleaned_data.get("numero_fiche"),
            section_id=filtre_form.cleaned_data["section"].pk if filtre_form.cleaned_data.get("section") else None,
            mois=int(mois) if mois else None,
            annee=int(annee) if annee else None,
        )
    elif not request.GET:
        today = date.today()
        fiches = get_fiches_saisie_horaire(annee=today.year, mois=today.month)

    total_lignes = sum(f["nb_lignes"] for f in fiches)
    total_montant = sum(f["total_montant"] for f in fiches)

    return render(
        request,
        "prestation/prestation_depuis_horaire_list.html",
        {
            "filtre_form": filtre_form,
            "fiches": fiches,
            "total_fiches": len(fiches),
            "total_lignes": total_lignes,
            "total_montant": total_montant,
        },
    )


@login_required
def prestation_depuis_horaire_saisie(request):
    annee_academique = _get_calcul_annee()
    filtre_form = PrestationDepuisHoraireFiltreForm(request.GET or None)
    if request.GET:
        date_form = PrestationDepuisHoraireDateForm(request.GET)
    else:
        date_form = PrestationDepuisHoraireDateForm(initial={"date_prestation": date.today()})
    tableau = None
    enveloppe_manquante = False
    paie_cloturee = False
    mode_modification = False
    msg_blocage_ajout = ""
    msg_blocage_annulation = ""
    alertes_blocage = []
    peut_ajouter = False
    peut_annuler = False
    date_prestation = _parse_date_prestation_param(request.GET.get("date_prestation"))

    if filtre_form.is_valid():
        numero_fiche = filtre_form.cleaned_data["numero_fiche"]
        section = filtre_form.cleaned_data["section"]
        jour = filtre_form.cleaned_data["jour"]
        if date_form.is_bound and date_form.is_valid():
            date_prestation = date_form.cleaned_data["date_prestation"]
        enveloppe_manquante = get_enveloppe_for_date(date_prestation) is None
        paie_cloturee = is_paie_mois_cloturee(date_prestation.year, date_prestation.month)
        msg_blocage_ajout = _blocage_ajout_prestation_horaire(
            request, date_prestation, enveloppe_manquante
        )
        msg_blocage_annulation = _blocage_annulation_prestation_horaire(request, date_prestation)

        if not annee_academique:
            messages.error(request, "Aucune année académique active n'est configurée.")
        else:
            rows = collect_prestation_horaire_rows(
                section, jour, numero_fiche, date_prestation, annee_academique
            )
            if not rows:
                messages.info(
                    request,
                    "Aucune ligne d'horaire trouvée pour cette section, ce jour et l'année académique active.",
                )
            jour_labels = dict(HoraireLigne.JOUR_CHOICES)
            nb_validees = sum(1 for row in rows if row["validee"])
            mode_modification = nb_validees > 0
            can_add = request.user.has_perm("prestation.add_prestation")
            can_cancel = (
                request.user.has_perm("prestation.delete_prestation")
                or request.user.has_perm("prestation.change_prestation")
            )
            _enrich_prestation_horaire_rows(
                rows,
                date_prestation=date_prestation,
                enveloppe_manquante=enveloppe_manquante,
                paie_cloturee=paie_cloturee,
                can_add=can_add and not msg_blocage_ajout,
                can_cancel=can_cancel and not msg_blocage_annulation,
                msg_blocage_ajout=msg_blocage_ajout,
                msg_blocage_annulation=msg_blocage_annulation,
            )
            nb_sans_prof = sum(1 for row in rows if not row["professeur_id"])
            if msg_blocage_ajout:
                alertes_blocage.append({"niveau": "warning", "texte": msg_blocage_ajout})
            if msg_blocage_annulation:
                alertes_blocage.append({"niveau": "warning", "texte": msg_blocage_annulation})
            if nb_sans_prof:
                alertes_blocage.append({
                    "niveau": "danger",
                    "texte": (
                        f"{nb_sans_prof} ligne(s) sans professeur : la case « Validé » est "
                        "désactivée. Corrigez l'horaire pour assigner un professeur à chaque cours."
                    ),
                })
            peut_ajouter = not msg_blocage_ajout
            peut_annuler = not msg_blocage_annulation
            if peut_ajouter and rows:
                alertes_blocage.append({
                    "niveau": "info",
                    "texte": (
                        "Pour enregistrer une prestation, cochez la case « Validé » sur la ligne "
                        "concernée puis confirmez dans la fenêtre qui s'affiche."
                    ),
                })
            tableau = {
                "numero_fiche": numero_fiche,
                "section": section,
                "section_label": section.nom or section.code,
                "jour": jour,
                "jour_label": jour_labels.get(jour, jour),
                "date_prestation": date_prestation,
                "date_label": date_prestation.strftime("%d/%m/%Y"),
                "rows": rows,
                "annee_academique": annee_academique,
                "nb_validees": nb_validees,
            }

    return render(
        request,
        "prestation/prestation_depuis_horaire.html",
        {
            "filtre_form": filtre_form,
            "date_form": date_form,
            "tableau": tableau,
            "mode_modification": mode_modification,
            "enveloppe_manquante": enveloppe_manquante,
            "paie_cloturee": paie_cloturee,
            "annee_academique": annee_academique,
            "api_url": reverse("prestation:api_prestation_horaire_toggle"),
            "can_add": request.user.has_perm("prestation.add_prestation"),
            "can_delete": request.user.has_perm("prestation.delete_prestation"),
            "can_change": request.user.has_perm("prestation.change_prestation"),
            "msg_blocage_ajout": msg_blocage_ajout,
            "msg_blocage_annulation": msg_blocage_annulation,
            "alertes_blocage": alertes_blocage,
            "peut_ajouter": peut_ajouter,
            "peut_annuler": peut_annuler,
        },
    )


@login_required
@require_POST
def api_prestation_horaire_toggle(request):
    action = request.POST.get("action")
    ligne_id = request.POST.get("ligne_id")
    numero_fiche = (request.POST.get("numero_fiche") or "").strip()
    section_id = request.POST.get("section")
    jour = request.POST.get("jour")
    date_str = request.POST.get("date")
    if not ligne_id or not section_id or not jour or not date_str:
        return JsonResponse(
            {"success": False, "message": "Paramètres incomplets."},
            status=400,
        )

    try:
        ligne_id = int(ligne_id)
        section_id = int(section_id)
        date_prestation = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "message": "Paramètres invalides."},
            status=400,
        )

    annee_academique = _get_calcul_annee()
    if not annee_academique:
        return JsonResponse(
            {"success": False, "message": "Aucune année académique active n'est configurée."},
            status=400,
        )

    try:
        if action == "confirm":
            if not request.user.has_perm("prestation.add_prestation"):
                return JsonResponse(
                    {"success": False, "message": "Vous n'avez pas la permission d'enregistrer une prestation."},
                    status=403,
                )
            if not numero_fiche:
                return JsonResponse(
                    {"success": False, "message": "Le numéro de fiche est obligatoire."},
                    status=400,
                )
            prestation = confirm_prestation_horaire_ligne(
                ligne_id=ligne_id,
                numero_fiche=numero_fiche,
                section_id=section_id,
                jour=jour,
                date_prestation=date_prestation,
                annee_academique=annee_academique,
            )
            return JsonResponse({
                "success": True,
                "message": "Prestation confirmée avec succès.",
                "checked": True,
                "prestation_id": prestation.pk,
            })

        if action == "cancel":
            if not (
                request.user.has_perm("prestation.delete_prestation")
                or request.user.has_perm("prestation.change_prestation")
            ):
                return JsonResponse(
                    {"success": False, "message": "Vous n'avez pas la permission d'annuler une prestation."},
                    status=403,
                )
            cancel_prestation_horaire_ligne(
                ligne_id=ligne_id,
                jour=jour,
                numero_fiche=numero_fiche,
                date_prestation=date_prestation,
            )
            return JsonResponse({
                "success": True,
                "message": "Prestation annulée avec succès.",
                "checked": False,
                "prestation_id": None,
            })

        return JsonResponse(
            {"success": False, "message": "Action non reconnue."},
            status=400,
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@login_required
def fiche_prestations_journaliere(request):
    form = FichePrestationJournaliereForm(request.GET or None)
    fiche = None
    download_query = ""

    if form.is_valid():
        jour = form.cleaned_data["jour"]
        section = form.cleaned_data["section"]
        semestre = form.cleaned_data["semestre"]
        annee_academique = _get_calcul_annee()
        if not annee_academique:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            fiche_data = _collect_fiche_prestations(section, jour, semestre, annee_academique)
            if not fiche_data["lines"]:
                messages.info(request, "Aucune prestation n'a été trouvée pour ce jour, ce semestre et cette section.")

            fiche = {
                "jour": jour,
                "jour_label": fiche_data["day_label"],
                "generated_label": date.today().strftime("%d/%m/%Y"),
                "day_label": fiche_data["day_label"],
                "section": section,
                "section_label": section.nom or section.code or "SECTION",
                "semestre": semestre,
                "annee_academique": annee_academique,
                "rows": fiche_data["lines"],
                "total_lignes": len(fiche_data["lines"]),
            }
            download_query = f"jour={jour}&section={section.pk}&semestre={semestre.pk}"

    return render(request, "prestation/fiche_prestations_journaliere.html", {
        "form": form,
        "fiche": fiche,
        "download_query": download_query,
    })


@login_required
def fiche_prestations_journaliere_pdf(request):
    form = FichePrestationJournaliereForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un jour, un semestre et une section pour générer la fiche journalière.")
        return redirect("prestation:fiche_prestations_journaliere")

    annee_academique = _get_calcul_annee()
    if not annee_academique:
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        return redirect("prestation:fiche_prestations_journaliere")

    jour = form.cleaned_data["jour"]
    section = form.cleaned_data["section"]
    semestre = form.cleaned_data["semestre"]
    fiche_data = _collect_fiche_prestations(section, jour, semestre, annee_academique)
    fiche = {
        "jour": jour,
        "jour_label": fiche_data["day_label"],
        "date_label": date.today().strftime("%d/%m/%Y"),
        "generated_label": date.today().strftime("%d/%m/%Y"),
        "day_label": fiche_data["day_label"],
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "semestre": semestre,
        "annee_academique": annee_academique,
        "rows": fiche_data["lines"],
    }
    pdf_buffer = _build_fiche_prestations_journaliere_pdf(fiche)
    filename = f"fiche_prestations_{jour}_{section.pk}_{semestre.pk}_{annee_academique.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def etat_paie_mensuel(request):
    annee_academique = _get_calcul_annee()
    form = CalculPaieForm(request.GET or None)
    etat = None
    budget = None
    download_query = ""

    if form.is_valid():
        annee = int(form.cleaned_data["annee"])
        mois = int(form.cleaned_data["mois"])
        section = form.cleaned_data["section"]
        paie_data = _collect_paie_data(mois, section, annee)
        budget = get_budget_context(annee, mois)
        if paie_data["fallback_used"]:
            messages.warning(
                request,
                "Aucune prestation n'est rattachée à cette section dans les données. L'état affiche donc toutes les prestations du mois sélectionné.",
            )
        elif not paie_data["prestations"]:
            messages.info(request, "Aucune prestation trouvée pour ce mois et cette section.")
        if budget["depasse"]:
            messages.error(request, budget["message"])

        lignes = []
        for index, item in enumerate(paie_data["resultats"], start=1):
            personnel = item["personnel"]
            lignes.append({
                "numero": index,
                "personnel_id": personnel.pk,
                "nom": personnel.last_name,
                "prenom": personnel.first_name,
                "net": item["total"],
            })

        etat = {
            "mois": MONTH_LABELS.get(str(mois), str(mois)),
            "mois_numero": mois,
            "annee": annee,
            "section": section,
            "section_label": section.nom or section.code or "SECTION",
            "annee_academique": annee_academique,
            "lignes": lignes,
            "total_general": paie_data["total_general"],
        }
        download_query = f"annee={annee}&mois={mois}&section={section.pk}"

    return render(request, "prestation/etat_paie_mensuel.html", {
        "form": form,
        "etat": etat,
        "budget": budget,
        "annee_academique": annee_academique,
        "download_query": download_query,
    })


def _build_etat_paie_pdf(etat):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "EtatPaieTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.2,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "CenterSmall",
        parent=body_style,
        alignment=TA_CENTER,
    )

    story = []
    direction = "DIRECTION DES SYSTEMES D'INFORMATION"
    ecole = "ECOLE INFORMATIQUE DES FINANCES"
    systeme_affichage = f"SYSTÈME LMD/{etat['section_label']}"
    year_text = etat["annee_academique"].code if etat.get("annee_academique") else "AUTOMATIQUE"
    story.append(_build_header_table(body_style, direction, ecole, systeme_affichage, "ANNEE ACADEMIQUE", year_text))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"<u><b>ETAT DE PAIE MENSUEL - {etat['mois']} {etat['annee_academique'].code if etat.get('annee_academique') else ''}</b></u>",
        title_style,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Section : <b>{etat['section_label']}</b>",
        ParagraphStyle(
            "EtatMeta",
            parent=body_style,
            fontSize=8.6,
            leading=10.2,
            textColor=colors.HexColor("#334155"),
        ),
    ))
    story.append(Spacer(1, 3 * mm))

    table_data = [[
        Paragraph("<b>N°</b>", center_style),
        Paragraph("<b>NOM</b>", center_style),
        Paragraph("<b>PRENOM</b>", center_style),
        Paragraph("<b>NET A PAYER</b>", center_style),
    ]]
    for ligne in etat["lignes"]:
        table_data.append([
            Paragraph(str(ligne["numero"]), center_style),
            Paragraph(ligne["nom"], body_style),
            Paragraph(ligne["prenom"], body_style),
            Paragraph(f"{int(ligne['net']):,} CDF".replace(",", " "), body_style),
        ])
    table_data.append([
        Paragraph("<b>TOTAL GENERAL</b>", body_style),
        Paragraph("", body_style),
        Paragraph("", body_style),
        Paragraph(f"<b>{int(etat['total_general']):,} CDF</b>".replace(",", " "), body_style),
    ])

    payroll_table = Table(table_data, colWidths=[15 * mm, 55 * mm, 65 * mm, 42 * mm], repeatRows=1)
    payroll_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0f2fe")),
        ("SPAN", (0, -1), (2, -1)),
        ("ALIGN", (0, -1), (2, -1), "RIGHT"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(payroll_table)
    story.append(Spacer(1, 6 * mm))
    story.append(_build_signature_footer(body_style))

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def etat_paie_mensuel_pdf(request):
    form = CalculPaieForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord un mois et une section pour générer l'état de paie.")
        return redirect("prestation:etat_paie_mensuel")

    annee = int(form.cleaned_data["annee"])
    mois = int(form.cleaned_data["mois"])
    section = form.cleaned_data["section"]
    paie_data = _collect_paie_data(mois, section, annee)
    lignes = []
    for index, item in enumerate(paie_data["resultats"], start=1):
        personnel = item["personnel"]
        lignes.append({
            "numero": index,
            "personnel_id": personnel.pk,
            "nom": personnel.last_name,
            "prenom": personnel.first_name,
            "net": item["total"],
        })
    etat = {
        "mois": MONTH_LABELS.get(str(mois), str(mois)),
        "section": section,
        "section_label": section.nom or section.code or "SECTION",
        "annee_academique": _get_calcul_annee(),
        "lignes": lignes,
        "total_general": paie_data["total_general"],
    }
    pdf_buffer = _build_etat_paie_pdf(etat)
    filename = f"etat_paie_{annee}_{mois}_{section.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_statistiques_enseignement_pdf(statistiques):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "StatsEnseignementTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14.4,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "StatsEnseignementBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "StatsEnseignementCenter",
        parent=body_style,
        alignment=TA_CENTER,
    )

    section = statistiques["section"]
    annee_academique = statistiques["annee_academique"]
    semestre = statistiques["semestre"]
    date_range_text = _format_statistiques_enseignement_range(statistiques["date_debut"], statistiques["date_fin"])
    story = [
        _build_header_table(
            body_style,
            "DIRECTION DES SYSTEMES D'INFORMATION",
            "ECOLE INFORMATIQUE DES FINANCES",
            "SYSTÈME LMD",
            "SECTION",
            section.nom or section.code or "SECTION",
        ),
        Spacer(1, 4 * mm),
        Paragraph(f"<u><b>STATISTIQUES DES PRESTATIONS {date_range_text}</b></u>", title_style),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Section : <b>{section.nom or section.code or 'SECTION'}</b>",
            ParagraphStyle(
                "StatsSection",
                parent=body_style,
                fontSize=8.6,
                leading=10.4,
                textColor=colors.HexColor("#334155"),
            ),
        ),
        Spacer(1, 3 * mm),
    ]

    table_data = [[
        Paragraph("<b>N°</b>", center_style),
        Paragraph("<b>NOM</b>", center_style),
        Paragraph("<b>UE</b>", center_style),
        Paragraph("<b>NOMBRE DE PRESTATIONS</b>", center_style),
    ]]

    for row in statistiques["rows"]:
        table_data.append([
            Paragraph(str(row["numero"]), center_style),
            Paragraph(row["nom_prenom"], body_style),
            Paragraph(row["ue"], body_style),
            Paragraph(str(row["nombre_prestations"]), center_style),
        ])

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", center_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("0", center_style),
        ])

    table = Table(table_data, colWidths=[12 * mm, 78 * mm, 54 * mm, 36 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def statistiques_prestations_enseignement(request):
    form = StatistiquesPrestationEnseignementForm(request.GET or None)
    statistiques = None
    download_query = ""

    if form.is_valid():
        date_debut = form.cleaned_data["date_debut"]
        date_fin = form.cleaned_data["date_fin"]
        section = form.cleaned_data["section"]
        semestre = form.cleaned_data["semestre"]
        annee_academique = _get_calcul_annee()
        if not annee_academique:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            stats_data = _collect_statistiques_prestations_enseignement(section, annee_academique, semestre, date_debut, date_fin)

            if not stats_data["rows"]:
                messages.info(request, "Aucune prestation d'enseignement n'a été trouvée pour les critères sélectionnés.")

            statistiques = {
                "section": section,
                "annee_academique": annee_academique,
                "semestre": semestre,
                "date_debut": date_debut,
                "date_fin": date_fin,
                "date_range_label": _format_statistiques_enseignement_range(date_debut, date_fin),
                "rows": stats_data["rows"],
                "total_lignes": stats_data["total_lignes"],
                "total_lignes_stats": stats_data["total_lignes_stats"],
            }
            download_query = f"date_debut={date_debut.isoformat()}&date_fin={date_fin.isoformat()}&section={section.pk}&semestre={semestre.pk}"

    return render(request, "prestation/statistiques_prestations_enseignement.html", {
        "form": form,
        "statistiques": statistiques,
        "download_query": download_query,
    })


@login_required
def statistiques_prestations_enseignement_pdf(request):
    form = StatistiquesPrestationEnseignementForm(request.GET or None)
    if not form.is_valid():
        messages.info(request, "Sélectionnez d'abord une section et un semestre pour générer les statistiques.")
        return redirect("prestation:statistiques_prestations_enseignement")

    annee_academique = _get_calcul_annee()
    if not annee_academique:
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        return redirect("prestation:statistiques_prestations_enseignement")

    date_debut = form.cleaned_data["date_debut"]
    date_fin = form.cleaned_data["date_fin"]
    section = form.cleaned_data["section"]
    semestre = form.cleaned_data["semestre"]
    stats_data = _collect_statistiques_prestations_enseignement(section, annee_academique, semestre, date_debut, date_fin)
    statistiques = {
        "section": section,
        "annee_academique": annee_academique,
        "semestre": semestre,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "rows": stats_data["rows"],
    }
    pdf_buffer = _build_statistiques_enseignement_pdf(statistiques)
    start_text = date_debut.strftime("%d-%m-%Y") if date_debut else "debut"
    end_text = date_fin.strftime("%d-%m-%Y") if date_fin else "fin"
    filename = f"statistiques_enseignement_{start_text}_{end_text}_{section.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_pdf(horaire):
    buffer = BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=5 * mm,
        bottomMargin=6 * mm,
    )
    content_width = page_size[0] - doc.leftMargin - doc.rightMargin
    content_height = page_size[1] - doc.topMargin - doc.bottomMargin

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HoraireTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#475569"),
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
    )
    center_style = ParagraphStyle(
        "CenterSmall",
        parent=body_style,
        alignment=TA_CENTER,
        leading=12.5,
    )
    right_footer_style = ParagraphStyle(
        "RightFooter",
        parent=body_style,
        alignment=TA_LEFT,
        leading=11,
        spaceBefore=0,
        spaceAfter=0,
        fontSize=8.5,
    )
    ue_cell_style = ParagraphStyle(
        "UeCell",
        parent=body_style,
        fontSize=9,
        leading=12.5,
        alignment=TA_LEFT,
    )
    teacher_cell_style = ParagraphStyle(
        "TeacherCell",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0f172a"),
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.white,
    )

    story = []

    logo = _logo_flowable(_asset_path("static", "images", "logoeifi.png"), width_mm=16)
    header_table = Table([[
        logo if logo else Paragraph("EIFI", ParagraphStyle("LogoFallback", parent=body_style, fontName="Helvetica-Bold", fontSize=12, textColor=colors.white)),
        Paragraph(f"<b>{horaire.direction}</b><br/>{horaire.ecole}<br/>{horaire.systeme_affichage}", ParagraphStyle(
            "HeaderTitle",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=9.8,
            leading=12,
            textColor=colors.white,
        )),
        Paragraph(f"<b>ANNEE ACADEMIQUE</b><br/>{horaire.annee_academique.code}", ParagraphStyle(
            "HeaderRight",
            parent=body_style,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        )),
    ]], colWidths=[22 * mm, content_width - 58 * mm, 36 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0f172a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#334155")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(f"<u><b>{horaire.titre_document}</b></u>", ParagraphStyle(
        "DocTitle",
        parent=title_style,
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=6,
    )))
    story.append(Spacer(1, 2 * mm))

    lines = list(
        horaire.lignes.select_related(
            "element_constitutif",
            "element_constitutif__ue",
            "element_constitutif__professeur",
            "local",
            "professeur",
        ).order_by("jour", "heure_debut", "ordre")
    )
    grouped = _group_lines_by_day(lines)

    col_jour = content_width * 0.09
    col_heures = content_width * 0.13
    col_ue = content_width * 0.31
    col_enseignant = content_width * 0.33
    col_loc = content_width * 0.14

    table_data = [[
        Paragraph("<b>JOURS</b>", header_cell_style),
        Paragraph("<b>HEURES</b>", header_cell_style),
        Paragraph("<b>UE</b>", header_cell_style),
        Paragraph("<b>ENSEIGNANT</b>", header_cell_style),
        Paragraph("<b>LOC</b>", header_cell_style),
    ]]

    span_commands = []
    row_index = 1
    for day in DAY_ORDER:
        day_lines = grouped.get(day, [])
        if not day_lines:
            continue
        start_row = row_index
        for idx, line in enumerate(day_lines):
            day_label = line.get_jour_display().upper() if idx == 0 else ""
            titulaire = line.titulaire_affichage if line.titulaire_affichage != "-" else ""
            table_data.append([
                Paragraph(f"<b>{day_label}</b>" if day_label else "", body_style),
                Paragraph(f"<b>{_format_time_range(line)}</b>", center_style),
                Paragraph(_format_ue_cell_html(line), ue_cell_style),
                Paragraph(f"<b>{titulaire}</b>" if titulaire else "", teacher_cell_style),
                Paragraph(f"<b>{line.local_affichage}</b>", center_style),
            ])
            row_index += 1
        if len(day_lines) > 1:
            span_commands.append(("SPAN", (0, start_row), (0, start_row + len(day_lines) - 1)))

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
            Paragraph("-", center_style),
        ])

    reserved_height = 18 * mm + 3 * mm + 12 * mm + 2 * mm + 26 * mm + 4 * mm
    schedule_height = max(content_height - reserved_height, 90 * mm)
    header_row_height = 10 * mm
    body_row_count = max(len(table_data) - 1, 1)
    body_row_height = max((schedule_height - header_row_height) / body_row_count, 9 * mm)
    row_heights = [header_row_height] + [body_row_height] * (len(table_data) - 1)

    schedule_table = Table(
        table_data,
        colWidths=[col_jour, col_heures, col_ue, col_enseignant, col_loc],
        rowHeights=row_heights,
        repeatRows=1,
    )
    schedule_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0c4a6e")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c4a6e")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#0284c7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "LEFT"),
        ("ALIGN", (3, 1), (3, -1), "LEFT"),
        ("ALIGN", (4, 1), (4, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 12.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#e0f2fe")),
        ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#0c4a6e")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (1, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ] + span_commands))
    story.append(schedule_table)

    settings_row = CardSettings.objects.first()
    chief_name = settings_row.training_division_chief_name if settings_row else ""

    note_text = (
        f"Le présent horaire a été établi pour la classe <b>{horaire.classe}</b> "
        f"de la filière <b>{horaire.filiere or '-'}</b>."
    )
    if horaire.observation:
        note_text += f"<br/>{horaire.observation}"

    footer_block = [
        Paragraph(f"Fait à Kinshasa le {date.today().strftime('%d/%m/%Y')}", right_footer_style),
        Paragraph("<u><b>LE CHEF DE DIVISION FORMATION</b></u>", right_footer_style),
    ]
    if chief_name:
        footer_block.append(Paragraph(chief_name, right_footer_style))

    footer_table = Table(
        [[
            Paragraph(note_text, ParagraphStyle(
                "NoteStyle",
                parent=body_style,
                fontSize=8.5,
                leading=11.5,
                textColor=colors.HexColor("#334155"),
            )),
            footer_block,
        ]],
        colWidths=[content_width * 0.62, content_width * 0.38],
    )
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 4 * mm))
    story.append(footer_table)

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer


@login_required
def horaire_list(request):
    horaires = Horaire.objects.select_related(
        "classe",
        "classe__promotion",
        "classe__promotion__filiere",
        "annee_academique",
        "semestre",
    ).prefetch_related("lignes").all()
    return render(request, "prestation/horaire_list.html", {"horaires": horaires})


@login_required
def horaire_detail(request, pk):
    horaire = get_object_or_404(
        Horaire.objects.select_related(
            "classe",
            "classe__promotion",
            "classe__promotion__filiere",
            "classe__promotion__filiere__section",
            "annee_academique",
            "semestre",
        ).prefetch_related(
            "lignes",
            "lignes__element_constitutif",
            "lignes__element_constitutif__ue",
            "lignes__element_constitutif__professeur",
            "lignes__local",
            "lignes__professeur",
        ),
        pk=pk,
    )
    lines = list(horaire.lignes.all().order_by("jour", "heure_debut", "ordre"))
    return render(
        request,
        "prestation/horaire_detail.html",
        {
            "horaire": horaire,
            "lines": lines,
            "grouped_lines": _group_lines_by_day(lines),
            "legend_items": _unique_legend_items(lines),
        },
    )


def _render_horaire_form(request, *, form, formset, title, horaire=None):
    return render(
        request,
        "prestation/horaire_form.html",
        {
            "form": form,
            "formset": formset,
            "title": title,
            "horaire": horaire,
            "ec_professeur_map": _build_ec_professeur_map(),
        },
    )


@login_required
def horaire_create(request):
    horaire = Horaire()
    if request.method == "POST":
        form = HoraireForm(request.POST, instance=horaire)
        formset = get_horaire_ligne_formset(instance=horaire, data=request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                horaire = form.save()
                formset.instance = horaire
                formset.save()
            messages.success(request, "Horaire créé avec succès.")
            return redirect("prestation:horaire_detail", pk=horaire.pk)
        messages.error(
            request,
            "L'enregistrement a échoué. Vérifiez les erreurs indiquées dans le formulaire.",
        )
    else:
        form = HoraireForm(instance=horaire)
        formset = get_horaire_ligne_formset(instance=horaire)
    return _render_horaire_form(request, form=form, formset=formset, title="Nouvel horaire")


@login_required
def horaire_update(request, pk):
    horaire = get_object_or_404(Horaire, pk=pk)
    if request.method == "POST":
        form = HoraireForm(request.POST, instance=horaire)
        formset = get_horaire_ligne_formset(instance=horaire, data=request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                horaire = form.save()
                formset.instance = horaire
                formset.save()
            messages.success(request, "Horaire modifié avec succès.")
            return redirect("prestation:horaire_detail", pk=horaire.pk)
        messages.error(
            request,
            "La modification a échoué. Vérifiez les erreurs indiquées dans le formulaire.",
        )
    else:
        form = HoraireForm(instance=horaire)
        formset = get_horaire_ligne_formset(instance=horaire)
    return _render_horaire_form(
        request,
        form=form,
        formset=formset,
        title="Modifier l'horaire",
        horaire=horaire,
    )


@login_required
def horaire_delete(request, pk):
    horaire = get_object_or_404(Horaire, pk=pk)
    if request.method == "POST":
        horaire.delete()
        messages.success(request, "Horaire supprimé avec succès.")
        return redirect("prestation:horaire_list")
    return render(request, "prestation/horaire_confirm_delete.html", {"horaire": horaire})


@login_required
def horaire_pdf(request, pk):
    horaire = get_object_or_404(
        Horaire.objects.select_related(
            "classe",
            "classe__promotion",
            "classe__promotion__filiere",
            "semestre",
            "annee_academique",
        ).prefetch_related("lignes", "lignes__element_constitutif", "lignes__local", "lignes__professeur"),
        pk=pk,
    )
    pdf_buffer = _build_pdf(horaire)
    filename = f"horaire_{horaire.pk}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
