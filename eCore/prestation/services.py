import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum

from academics.models import Section

from .models import (
    BaremePrestation,
    EnveloppeBudgetaire,
    HoraireLigne,
    PaieMensuelle,
    PersonnelBaremeInitial,
    Prestation,
)

MONTH_LABELS = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}


def get_month_label(mois):
    return MONTH_LABELS.get(int(mois), str(mois))


def is_prestation_mensuelle(prestation):
    observation = (prestation.observation or "").strip()
    return observation.startswith(PRESTATION_MENSUELLE_OBSERVATION_PREFIX)


def is_prestation_horaire(prestation):
    if is_prestation_mensuelle(prestation):
        return False
    return bool(prestation.horaire_ligne_id or prestation.horaire_id)


def get_prestation_section(prestation):
    horaire = getattr(prestation, "horaire", None)
    if not horaire or not getattr(horaire, "classe", None):
        return None
    promotion = getattr(horaire.classe, "promotion", None)
    filiere = getattr(promotion, "filiere", None) if promotion else None
    return getattr(filiere, "section", None) if filiere else None


def prestation_section_matches(prestation, section):
    prestation_section = get_prestation_section(prestation)
    if prestation_section and prestation_section.pk == section.pk:
        return True
    return False


def prestation_in_calcul_paie(prestation, section):
    """
    Inclut les prestations horaire de la section sélectionnée
    et toutes les prestations mensuelles du mois (sans rattachement section).
    """
    if is_prestation_mensuelle(prestation):
        return True
    return prestation_section_matches(prestation, section)


def build_baremes_initiaux_horaire_cache(personnel_ids):
    """Barème initial par personnel pour le calcul des prestations horaire."""
    if not personnel_ids:
        return {}
    personnel_ids = list(set(personnel_ids))
    cache = {}
    enseignement_liens = PersonnelBaremeInitial.objects.filter(
        personnel_id__in=personnel_ids,
        bareme__categorie=BaremePrestation.CATEGORIE_ENSEIGNEMENT,
    ).select_related("bareme").order_by(
        "personnel_id",
        "bareme__ordre",
        "bareme__intitule",
    )
    for lien in enseignement_liens:
        if lien.personnel_id not in cache:
            cache[lien.personnel_id] = lien

    missing = set(personnel_ids) - set(cache.keys())
    if missing:
        autres = PersonnelBaremeInitial.objects.filter(
            personnel_id__in=missing,
        ).select_related("bareme").order_by(
            "personnel_id",
            "bareme__ordre",
            "bareme__intitule",
        )
        for lien in autres:
            if lien.personnel_id not in cache:
                cache[lien.personnel_id] = lien
    return cache


def _montant_prestation_horaire_paie(prestation, cache_baremes_initiaux):
    lien = cache_baremes_initiaux.get(prestation.personnel_id)
    if not lien:
        return Decimal(0), None, 1, Decimal(0), (
            "Barème initial manquant pour ce personnel — montant horaire compté à 0."
        )
    montant_unitaire = Decimal(lien.bareme.montant or 0)
    quantite = int(lien.quantite or 1)
    montant = montant_unitaire * quantite
    return montant, lien.bareme, quantite, montant_unitaire, None


def _montant_prestation_mensuelle_paie(prestation):
    montant_unitaire = Decimal(prestation.bareme.montant or 0)
    return montant_unitaire, prestation.bareme, 1, montant_unitaire, None


def build_ligne_paie(prestation, cache_baremes_initiaux):
    if is_prestation_horaire(prestation):
        montant, bareme, quantite, montant_unitaire, warning = _montant_prestation_horaire_paie(
            prestation, cache_baremes_initiaux
        )
        source = "horaire"
        source_label = "Horaire"
        formule = f"{int(montant_unitaire):,} × {quantite}".replace(",", " ")
    elif is_prestation_mensuelle(prestation):
        montant, bareme, quantite, montant_unitaire, warning = _montant_prestation_mensuelle_paie(
            prestation
        )
        source = "mensuelle"
        source_label = "Saisie mensuelle"
        formule = f"{int(montant_unitaire):,} × {quantite}".replace(",", " ")
    else:
        montant_unitaire = Decimal(prestation.bareme.montant or 0)
        montant = Decimal(prestation.montant or 0)
        bareme = prestation.bareme
        quantite = 1
        warning = None
        source = "autre"
        source_label = "Autre saisie"
        formule = f"{int(montant):,}".replace(",", " ")

    bareme_label = str(bareme) if bareme else "-"
    return {
        "prestation": prestation,
        "source": source,
        "source_label": source_label,
        "montant": montant,
        "montant_unitaire": montant_unitaire,
        "quantite": quantite,
        "bareme": bareme,
        "bareme_label": bareme_label,
        "bareme_categorie": bareme.categorie if bareme else "",
        "formule": formule,
        "avertissement": warning,
        "date_prestation": prestation.date_prestation,
        "categorie_display": prestation.get_categorie_display(),
    }


def calcul_montant_prestation_paie(prestation, cache_baremes_initiaux):
    return build_ligne_paie(prestation, cache_baremes_initiaux)["montant"]


def get_total_prestations_mois(annee, mois):
    prestations = Prestation.objects.filter(
        date_prestation__year=annee,
        date_prestation__month=mois,
    ).select_related("bareme", "horaire", "horaire__classe", "horaire__classe__promotion", "horaire__classe__promotion__filiere")
    personnel_ids = prestations.values_list("personnel_id", flat=True).distinct()
    cache = build_baremes_initiaux_horaire_cache(personnel_ids)
    total = Decimal(0)
    for prestation in prestations:
        total += calcul_montant_prestation_paie(prestation, cache)
    return total


def get_budget_context(annee, mois):
    annee = int(annee)
    mois = int(mois)
    enveloppe = EnveloppeBudgetaire.objects.filter(annee=annee, mois=mois).first()
    total_engage = get_total_prestations_mois(annee, mois)
    paie_validee = None
    if enveloppe:
        try:
            paie_validee = enveloppe.paie_validee
        except PaieMensuelle.DoesNotExist:
            paie_validee = None

    if not enveloppe:
        return {
            "annee": annee,
            "mois": mois,
            "mois_label": get_month_label(mois),
            "enveloppe": None,
            "montant_enveloppe": Decimal("0"),
            "total_engage": total_engage,
            "solde_disponible": Decimal("0"),
            "depasse": True,
            "paie_validee": paie_validee,
            "deja_validee": False,
            "deja_cloturee": False,
            "peut_valider": False,
            "peut_cloturer": False,
            "total_paye": total_engage,
            "message": "Aucune enveloppe budgétaire n'est définie pour cette période.",
        }

    montant_enveloppe = Decimal(enveloppe.montant)
    solde_disponible = montant_enveloppe - total_engage
    depasse = total_engage > montant_enveloppe
    deja_validee = paie_validee is not None

    context = {
        "annee": annee,
        "mois": mois,
        "mois_label": get_month_label(mois),
        "enveloppe": enveloppe,
        "montant_enveloppe": montant_enveloppe,
        "total_engage": total_engage,
        "solde_disponible": solde_disponible,
        "depasse": depasse,
        "paie_validee": paie_validee,
        "deja_validee": deja_validee,
        "peut_valider": not deja_validee and not depasse,
    }

    context["deja_cloturee"] = deja_validee
    context["peut_cloturer"] = context["peut_valider"]
    context["total_paye"] = total_engage

    if deja_validee:
        context["message"] = "La paie mensuelle de cette période est déjà clôturée."
    elif depasse:
        context["message"] = (
            f"Le total des prestations ({int(total_engage):,} CDF) dépasse l'enveloppe budgétaire "
            f"({int(montant_enveloppe):,} CDF). Solde disponible : {int(solde_disponible):,} CDF."
        ).replace(",", " ")
    else:
        context["message"] = (
            f"Solde disponible : {int(solde_disponible):,} CDF "
            f"(enveloppe {int(montant_enveloppe):,} CDF − engagé {int(total_engage):,} CDF)."
        ).replace(",", " ")

    return context


def is_paie_mois_cloturee(annee, mois):
    enveloppe = EnveloppeBudgetaire.objects.filter(annee=int(annee), mois=int(mois)).first()
    if not enveloppe:
        return False
    return PaieMensuelle.objects.filter(enveloppe=enveloppe).exists()


def assert_mois_non_cloture(annee, mois):
    if is_paie_mois_cloturee(annee, mois):
        raise ValueError(
            f"La paie de {get_month_label(mois)} {annee} est clôturée. "
            "Aucune saisie ni modification n'est autorisée pour ce mois."
        )


def get_enveloppe_for_date(date_prestation):
    return EnveloppeBudgetaire.objects.filter(
        annee=date_prestation.year,
        mois=date_prestation.month,
    ).first()


def assert_enveloppe_disponible(date_prestation):
    if not get_enveloppe_for_date(date_prestation):
        raise ValueError("Aucune enveloppe budgétaire n'a été trouvée.")


def assert_prestation_modifiable(date_prestation):
    assert_enveloppe_disponible(date_prestation)


def cloturer_paie_mensuelle(annee, mois, user):
    budget = get_budget_context(annee, mois)
    if not budget["enveloppe"]:
        raise ValueError(budget["message"])
    if budget["deja_cloturee"]:
        raise ValueError("La paie de ce mois est déjà clôturée.")
    if budget["depasse"]:
        raise ValueError(budget["message"])

    paie = PaieMensuelle.objects.create(
        enveloppe=budget["enveloppe"],
        montant_total_valide=budget["total_engage"],
        valide_par=user if user and user.is_authenticated else None,
    )
    return paie, budget


def valider_paie_mensuelle(annee, mois, user):
    return cloturer_paie_mensuelle(annee, mois, user)


DATE_WEEKDAY_TO_JOUR = {
    0: HoraireLigne.JOUR_LUNDI,
    1: HoraireLigne.JOUR_MARDI,
    2: HoraireLigne.JOUR_MERCREDI,
    3: HoraireLigne.JOUR_JEUDI,
    4: HoraireLigne.JOUR_VENDREDI,
    5: HoraireLigne.JOUR_SAMEDI,
}


def get_baremes_initiaux_personnel(personnel):
    return PersonnelBaremeInitial.objects.filter(
        personnel=personnel,
    ).select_related("bareme").order_by(
        "bareme__categorie",
        "bareme__ordre",
        "bareme__intitule",
    )


def parse_baremes_initiaux_post(data):
    """Extrait les barèmes cochés et leurs quantités depuis un POST."""
    items = []
    for bareme_id in data.getlist("baremes_initiaux"):
        try:
            bareme_id = int(bareme_id)
            quantite = int(data.get(f"quantite_bareme_{bareme_id}", 1))
            quantite = max(1, quantite)
        except (TypeError, ValueError):
            continue
        items.append({"bareme_id": bareme_id, "quantite": quantite})
    return items


PRESTATION_MENSUELLE_OBSERVATION_PREFIX = "Prestation mensuelle"


def get_prestations_mensuelles_queryset(
    annee=None,
    mois=None,
    numero_fiche=None,
    personnel_id=None,
    bareme_id=None,
):
    qs = Prestation.objects.filter(
        observation__startswith=PRESTATION_MENSUELLE_OBSERVATION_PREFIX,
    ).select_related("personnel", "bareme").order_by(
        "-date_prestation",
        "-created_at",
    )
    if annee:
        qs = qs.filter(date_prestation__year=int(annee))
    if mois:
        qs = qs.filter(date_prestation__month=int(mois))
    if numero_fiche:
        qs = qs.filter(numero_fiche__icontains=numero_fiche.strip())
    if personnel_id:
        qs = qs.filter(personnel_id=int(personnel_id))
    if bareme_id:
        qs = qs.filter(bareme_id=int(bareme_id))
    return qs


def get_saisies_prestation_mensuelle(*, annee=None, mois=None, numero_fiche=None):
    """Regroupe les prestations mensuelles par saisie (période, fiche, personnel, barème)."""
    from django.db.models import Count, F, Max, Sum

    qs = Prestation.objects.filter(
        observation__startswith=PRESTATION_MENSUELLE_OBSERVATION_PREFIX,
    )
    if annee:
        qs = qs.filter(date_prestation__year=int(annee))
    if mois:
        qs = qs.filter(date_prestation__month=int(mois))
    if numero_fiche:
        qs = qs.filter(numero_fiche__icontains=numero_fiche.strip())

    grouped = qs.values(
        "numero_fiche",
        "personnel_id",
        "bareme_id",
        annee=F("date_prestation__year"),
        mois_num=F("date_prestation__month"),
        personnel_nom=F("personnel__last_name"),
        personnel_prenom=F("personnel__first_name"),
        bareme_intitule=F("bareme__intitule"),
        bareme_categorie=F("bareme__categorie"),
    ).annotate(
        nb_lignes=Count("pk"),
        total_montant=Sum("montant"),
        derniere_modification=Max("updated_at"),
    ).order_by("-annee", "-mois_num", "numero_fiche")

    mois_labels = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
        5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
        9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
    }
    saisies = []
    for row in grouped:
        mois_num = row["mois_num"]
        saisies.append({
            "annee": row["annee"],
            "mois": mois_num,
            "mois_label": mois_labels.get(mois_num, str(mois_num)),
            "numero_fiche": row["numero_fiche"] or "-",
            "personnel_id": row["personnel_id"],
            "personnel_label": f"{row.get('personnel_prenom') or ''} {row.get('personnel_nom') or ''}".strip() or "-",
            "bareme_id": row["bareme_id"],
            "bareme_label": row.get("bareme_intitule") or "-",
            "bareme_categorie": row.get("bareme_categorie") or "",
            "nb_lignes": row["nb_lignes"],
            "total_montant": row["total_montant"] or 0,
            "derniere_modification": row["derniere_modification"],
        })
    return saisies


def get_baremes_prestation_mensuelle_queryset():
    return BaremePrestation.objects.filter(active=True).exclude(
        categorie=BaremePrestation.CATEGORIE_ENSEIGNEMENT,
    ).order_by("categorie", "ordre", "intitule")


def enregistrer_prestations_mensuelles(
    *,
    annee,
    mois,
    numero_fiche,
    personnel,
    bareme,
    quantite,
):
    annee = int(annee)
    mois = int(mois)
    quantite = int(quantite)
    numero_fiche = numero_fiche.strip()

    if quantite < 1:
        raise ValueError("La quantité doit être au moins égale à 1.")
    if bareme.categorie == BaremePrestation.CATEGORIE_ENSEIGNEMENT:
        raise ValueError("Les barèmes de type enseignement ne sont pas autorisés pour cette saisie.")

    date_controle = date(annee, mois, 1)
    assert_enveloppe_disponible(date_controle)
    assert_mois_non_cloture(annee, mois)

    dernier_jour = calendar.monthrange(annee, mois)[1]
    prestations = []
    for index in range(quantite):
        jour_mois = min(index + 1, dernier_jour)
        date_prestation = date(annee, mois, jour_mois)
        prestations.append(
            Prestation(
                date_prestation=date_prestation,
                personnel=personnel,
                bareme=bareme,
                categorie=bareme.categorie,
                montant=bareme.montant,
                numero_fiche=numero_fiche,
                observation=(
                    f"{PRESTATION_MENSUELLE_OBSERVATION_PREFIX} — Fiche n° {numero_fiche} "
                    f"({index + 1}/{quantite})"
                ),
            )
        )

    with transaction.atomic():
        Prestation.objects.bulk_create(prestations)

    return quantite


def get_prestations_mensuelle_groupe(*, annee, mois, numero_fiche, personnel_id, bareme_id):
    return Prestation.objects.filter(
        observation__startswith=PRESTATION_MENSUELLE_OBSERVATION_PREFIX,
        date_prestation__year=int(annee),
        date_prestation__month=int(mois),
        numero_fiche=numero_fiche.strip(),
        personnel_id=int(personnel_id),
        bareme_id=int(bareme_id),
    )


def supprimer_saisie_prestation_mensuelle(*, annee, mois, numero_fiche, personnel_id, bareme_id):
    assert_mois_non_cloture(int(annee), int(mois))
    deleted, _ = get_prestations_mensuelle_groupe(
        annee=annee,
        mois=mois,
        numero_fiche=numero_fiche,
        personnel_id=personnel_id,
        bareme_id=bareme_id,
    ).delete()
    if not deleted:
        raise ValueError("Saisie mensuelle introuvable.")
    return deleted


def modifier_saisie_prestation_mensuelle(
    *,
    orig_annee,
    orig_mois,
    orig_numero_fiche,
    orig_personnel_id,
    orig_bareme_id,
    annee,
    mois,
    numero_fiche,
    personnel,
    bareme,
    quantite,
):
    orig_annee, orig_mois = int(orig_annee), int(orig_mois)
    annee, mois = int(annee), int(mois)
    assert_mois_non_cloture(orig_annee, orig_mois)
    if (orig_annee, orig_mois) != (annee, mois):
        assert_mois_non_cloture(annee, mois)

    with transaction.atomic():
        supprimer_saisie_prestation_mensuelle(
            annee=orig_annee,
            mois=orig_mois,
            numero_fiche=orig_numero_fiche,
            personnel_id=orig_personnel_id,
            bareme_id=orig_bareme_id,
        )
        return enregistrer_prestations_mensuelles(
            annee=annee,
            mois=mois,
            numero_fiche=numero_fiche,
            personnel=personnel,
            bareme=bareme,
            quantite=quantite,
        )


def set_personnel_baremes_initiaux(personnel, items):
    PersonnelBaremeInitial.objects.filter(personnel=personnel).delete()
    if not items:
        return
    bareme_ids = [item["bareme_id"] for item in items]
    baremes = {
        b.pk: b
        for b in BaremePrestation.objects.filter(pk__in=bareme_ids, active=True)
    }
    PersonnelBaremeInitial.objects.bulk_create([
        PersonnelBaremeInitial(
            personnel=personnel,
            bareme=baremes[item["bareme_id"]],
            quantite=item["quantite"],
        )
        for item in items
        if item["bareme_id"] in baremes
    ])


def get_default_bareme_enseignement():
    bareme = BaremePrestation.objects.filter(
        categorie=BaremePrestation.CATEGORIE_ENSEIGNEMENT,
        periode=BaremePrestation.PERIODE_HEURE,
        active=True,
    ).order_by("ordre", "intitule").first()
    if bareme:
        return bareme
    return BaremePrestation.objects.filter(
        categorie=BaremePrestation.CATEGORIE_ENSEIGNEMENT,
        active=True,
    ).order_by("ordre", "intitule").first()


def _cours_label(ligne):
    if ligne.element_constitutif_id:
        ec = ligne.element_constitutif
        if ec.nom:
            return ec.nom
        return ec.code
    code = (ligne.ue_code or "").strip()
    return code or "-"


def _heure_cours_label(ligne):
    return f"{ligne.heure_debut.strftime('%H:%M')} - {ligne.heure_fin.strftime('%H:%M')}"


def get_fiches_saisie_horaire(*, numero_fiche=None, section_id=None, mois=None, annee=None):
    """Liste des fiches de saisie (groupées par n° fiche, date, jour et section)."""
    from django.db.models import Count, F, Max, Sum

    qs = Prestation.objects.filter(horaire_ligne__isnull=False).exclude(numero_fiche="")
    if numero_fiche:
        qs = qs.filter(numero_fiche__icontains=numero_fiche.strip())
    if section_id:
        qs = qs.filter(horaire__classe__promotion__filiere__section_id=section_id)
    if annee:
        qs = qs.filter(date_prestation__year=int(annee))
    if mois:
        qs = qs.filter(date_prestation__month=int(mois))

    grouped = qs.values(
        "numero_fiche",
        "date_prestation",
        "jour",
        section_id=F("horaire__classe__promotion__filiere__section_id"),
        section_nom=F("horaire__classe__promotion__filiere__section__nom"),
        section_code=F("horaire__classe__promotion__filiere__section__code"),
    ).annotate(
        nb_lignes=Count("pk"),
        total_montant=Sum("montant"),
        derniere_modification=Max("updated_at"),
    ).order_by("-date_prestation", "numero_fiche")

    day_labels = dict(HoraireLigne.JOUR_CHOICES)
    fiches = []
    for row in grouped:
        section_label = row.get("section_nom") or row.get("section_code") or "-"
        fiches.append({
            "numero_fiche": row["numero_fiche"],
            "date_prestation": row["date_prestation"],
            "jour": row["jour"],
            "jour_label": day_labels.get(row["jour"], row["jour"] or "-"),
            "section_id": row.get("section_id"),
            "section_label": section_label,
            "nb_lignes": row["nb_lignes"],
            "total_montant": row["total_montant"] or 0,
            "derniere_modification": row["derniere_modification"],
        })
    return fiches


def collect_prestation_horaire_rows(section, jour, numero_fiche, date_prestation, annee_academique):
    lines = HoraireLigne.objects.select_related(
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
        "element_constitutif",
        "element_constitutif__professeur",
        "professeur",
    ).filter(
        horaire__active=True,
        horaire__annee_academique=annee_academique,
        horaire__classe__promotion__filiere__section=section,
        jour=jour,
    ).order_by(
        "horaire__classe__promotion__code",
        "horaire__classe__code",
        "heure_debut",
        "ordre",
    )

    ligne_ids = [line.pk for line in lines]
    prestations_map = {}
    if ligne_ids:
        for prestation in Prestation.objects.filter(
            date_prestation=date_prestation,
            horaire_ligne_id__in=ligne_ids,
        ):
            prestations_map[prestation.horaire_ligne_id] = prestation.pk

    day_labels = dict(HoraireLigne.JOUR_CHOICES)
    rows = []
    for line in lines:
        professeur = line.professeur_affichage
        rows.append({
            "ligne_id": line.pk,
            "jour_label": day_labels.get(line.jour, line.jour),
            "cours": _cours_label(line),
            "classe": line.horaire.classe.nom if line.horaire and line.horaire.classe else "-",
            "professeur": line.titulaire_affichage,
            "professeur_id": professeur.pk if professeur else None,
            "heure_cours": _heure_cours_label(line),
            "validee": line.pk in prestations_map,
            "prestation_id": prestations_map.get(line.pk),
        })
    return rows


def confirm_prestation_horaire_ligne(
    *,
    ligne_id,
    numero_fiche,
    section_id,
    jour,
    date_prestation,
    annee_academique,
):
    numero_fiche = numero_fiche.strip()
    assert_enveloppe_disponible(date_prestation)
    assert_mois_non_cloture(date_prestation.year, date_prestation.month)

    try:
        section = Section.objects.get(pk=section_id)
    except Section.DoesNotExist as exc:
        raise ValueError("Section invalide.") from exc

    ligne = HoraireLigne.objects.select_related(
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
        "element_constitutif",
        "element_constitutif__professeur",
        "professeur",
    ).filter(
        pk=ligne_id,
        jour=jour,
        horaire__active=True,
        horaire__annee_academique=annee_academique,
        horaire__classe__promotion__filiere__section=section,
    ).first()
    if not ligne:
        raise ValueError("Ligne d'horaire introuvable pour cette sélection.")

    professeur = ligne.professeur_affichage
    if not professeur:
        raise ValueError("Aucun professeur n'est associé à ce cours.")

    existing = Prestation.objects.filter(
        date_prestation=date_prestation,
        horaire_ligne=ligne,
    ).first()
    if existing:
        update_fields = []
        if existing.numero_fiche != numero_fiche:
            existing.numero_fiche = numero_fiche
            existing.observation = f"Fiche n° {numero_fiche}"
            update_fields.extend(["numero_fiche", "observation"])
        if existing.jour != jour:
            existing.jour = jour
            update_fields.append("jour")
        if update_fields:
            existing.save(update_fields=update_fields)
        return existing

    bareme = get_default_bareme_enseignement()
    if not bareme:
        raise ValueError(
            "Aucun barème d'enseignement actif n'est configuré. Veuillez créer un barème avant de valider."
        )

    try:
        prestation = Prestation.objects.create(
            date_prestation=date_prestation,
            personnel=professeur,
            bareme=bareme,
            horaire=ligne.horaire,
            horaire_ligne=ligne,
            numero_fiche=numero_fiche,
            jour=jour,
            heure_debut=ligne.heure_debut,
            observation=f"Fiche n° {numero_fiche}",
        )
    except IntegrityError as exc:
        raise ValueError(
            "Une prestation existe déjà pour ce professeur, ce cours, cette classe et cette heure."
        ) from exc

    return prestation


def cancel_prestation_horaire_ligne(*, ligne_id, jour, numero_fiche, date_prestation):
    assert_mois_non_cloture(date_prestation.year, date_prestation.month)

    prestation = Prestation.objects.filter(
        date_prestation=date_prestation,
        horaire_ligne_id=ligne_id,
    ).first()
    if not prestation:
        raise ValueError("Aucune prestation validée à annuler pour cette ligne.")

    prestation.delete()


def collect_calcul_paie_data(mois, section, annee):
    """
    Agrège le calcul de paie par personnel :
    - horaire : barème initial du personnel × quantité initiale (par ligne validée)
    - mensuelle : barème de la prestation × 1 (une ligne DB = une unité ; total = barème × quantité saisie)
    """
    prestations_mois = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
    ).filter(
        date_prestation__year=annee,
        date_prestation__month=mois,
    ).order_by("personnel__last_name", "personnel__first_name", "date_prestation")

    prestations_list = list(prestations_mois)
    prestations_filtrees = [
        p for p in prestations_list if prestation_in_calcul_paie(p, section)
    ]
    horaire_section = [
        p for p in prestations_list
        if is_prestation_horaire(p) and prestation_section_matches(p, section)
    ]
    fallback_used = False
    if not horaire_section and any(is_prestation_horaire(p) for p in prestations_list):
        fallback_used = True

    personnel_ids = {p.personnel_id for p in prestations_filtrees}
    cache_baremes = build_baremes_initiaux_horaire_cache(personnel_ids)

    grouped = defaultdict(list)
    for prestation in prestations_filtrees:
        grouped[prestation.personnel].append(
            build_ligne_paie(prestation, cache_baremes)
        )

    resultats = []
    totals_by_bareme_map = defaultdict(lambda: {"nombre": 0, "total": Decimal(0), "categorie": "", "intitule": ""})
    alertes_globales = []

    for personnel, lignes in grouped.items():
        total_horaire = Decimal(0)
        total_mensuelles = Decimal(0)
        total_autre = Decimal(0)
        nb_horaire = 0
        nb_mensuelle = 0
        for ligne in lignes:
            montant = ligne["montant"]
            if ligne["source"] == "horaire":
                total_horaire += montant
                nb_horaire += 1
            elif ligne["source"] == "mensuelle":
                total_mensuelles += montant
                nb_mensuelle += 1
            else:
                total_autre += montant

            key = (ligne["bareme_categorie"], ligne["bareme_label"])
            totals_by_bareme_map[key]["nombre"] += 1
            totals_by_bareme_map[key]["total"] += montant
            totals_by_bareme_map[key]["categorie"] = ligne["bareme_categorie"]
            totals_by_bareme_map[key]["intitule"] = ligne["bareme_label"]

            if ligne["avertissement"]:
                alertes_globales.append(f"{personnel} : {ligne['avertissement']}")

        total_a_payer = total_horaire + total_mensuelles + total_autre
        resultats.append({
            "personnel": personnel,
            "lignes": lignes,
            "prestations": lignes,
            "total": total_a_payer,
            "total_horaire": total_horaire,
            "total_mensuelles": total_mensuelles,
            "total_autre": total_autre,
            "nb_horaire": nb_horaire,
            "nb_mensuelle": nb_mensuelle,
        })

    resultats.sort(
        key=lambda item: (
            (item["personnel"].last_name or "").lower(),
            (item["personnel"].first_name or "").lower(),
        )
    )

    total_general = sum(item["total"] for item in resultats)
    total_horaire_global = sum(item["total_horaire"] for item in resultats)
    total_mensuelles_global = sum(item["total_mensuelles"] for item in resultats)
    total_prestations = len(prestations_filtrees)
    total_personnels = len(resultats)

    totals_by_bareme = [
        {
            "bareme__categorie": data["categorie"],
            "bareme__intitule": data["intitule"],
            "nombre": data["nombre"],
            "total": data["total"],
        }
        for data in sorted(
            totals_by_bareme_map.values(),
            key=lambda row: (row["categorie"], row["intitule"]),
        )
    ]

    return {
        "prestations_mois": prestations_mois,
        "prestations": prestations_filtrees,
        "resultats": resultats,
        "total_general": total_general,
        "total_horaire_global": total_horaire_global,
        "total_mensuelles_global": total_mensuelles_global,
        "total_prestations": total_prestations,
        "total_personnels": total_personnels,
        "totals_by_bareme": totals_by_bareme,
        "fallback_used": fallback_used,
        "alertes_globales": list(dict.fromkeys(alertes_globales)),
    }


def collect_bulletin_individuel_paie(personnel, mois, section, annee):
    prestations = Prestation.objects.select_related(
        "personnel",
        "bareme",
        "horaire",
        "horaire__classe",
        "horaire__classe__promotion",
        "horaire__classe__promotion__filiere",
        "horaire__classe__promotion__filiere__section",
    ).filter(
        personnel=personnel,
        date_prestation__year=annee,
        date_prestation__month=mois,
    ).order_by("date_prestation")

    prestations_filtrees = [
        p for p in prestations if prestation_in_calcul_paie(p, section)
    ]
    cache = build_baremes_initiaux_horaire_cache([personnel.pk])
    lignes = [build_ligne_paie(p, cache) for p in prestations_filtrees]
    total_general = sum(ligne["montant"] for ligne in lignes)
    total_horaire = sum(l["montant"] for l in lignes if l["source"] == "horaire")
    total_mensuelles = sum(l["montant"] for l in lignes if l["source"] == "mensuelle")
    return {
        "personnel": personnel,
        "lignes": lignes,
        "prestations": lignes,
        "total_general": total_general,
        "total": total_general,
        "total_horaire": total_horaire,
        "total_mensuelles": total_mensuelles,
    }
