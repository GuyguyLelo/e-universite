from django.urls import path

from . import views

app_name = "prestation"

urlpatterns = [
    path("baremes/", views.bareme_list, name="bareme_list"),
    path("baremes/nouveau/", views.bareme_create, name="bareme_create"),
    path("baremes/<int:pk>/modifier/", views.bareme_update, name="bareme_update"),
    path("baremes/<int:pk>/supprimer/", views.bareme_delete, name="bareme_delete"),
    path("enveloppes/", views.enveloppe_list, name="enveloppe_list"),
    path("enveloppes/nouvelle/", views.enveloppe_create, name="enveloppe_create"),
    path("enveloppes/<int:pk>/modifier/", views.enveloppe_update, name="enveloppe_update"),
    path("enveloppes/<int:pk>/supprimer/", views.enveloppe_delete, name="enveloppe_delete"),
    path("cloture-paie-mensuelle/", views.cloture_paie_mensuelle, name="cloture_paie_mensuelle"),
    path("prestations/", views.prestation_list, name="prestation_list"),
    path("prestations/depuis-horaire/", views.prestation_depuis_horaire_list, name="prestation_depuis_horaire"),
    path(
        "prestations/depuis-horaire/saisie/",
        views.prestation_depuis_horaire_saisie,
        name="prestation_depuis_horaire_saisie",
    ),
    path("prestations/mensuelle/", views.prestation_mensuelle_list, name="prestation_mensuelle_list"),
    path("prestations/mensuelle/saisie/", views.prestation_mensuelle_saisie, name="prestation_mensuelle_saisie"),
    path(
        "prestations/mensuelle/modifier/",
        views.prestation_mensuelle_modifier,
        name="prestation_mensuelle_modifier",
    ),
    path(
        "prestations/mensuelle/supprimer/",
        views.prestation_mensuelle_supprimer,
        name="prestation_mensuelle_supprimer",
    ),
    path(
        "prestations/api/horaire-toggle/",
        views.api_prestation_horaire_toggle,
        name="api_prestation_horaire_toggle",
    ),
    path("prestations/nouvelle/", views.prestation_create, name="prestation_create"),
    path("prestations/<int:pk>/modifier/", views.prestation_update, name="prestation_update"),
    path("prestations/<int:pk>/supprimer/", views.prestation_delete, name="prestation_delete"),
    path("api/baremes/", views.api_baremes_by_categorie, name="api_baremes_by_categorie"),
    path("calcul-paie/", views.calcul_paie, name="calcul_paie"),
    path("bulletin-paie/", views.bulletin_paie, name="bulletin_paie"),
    path("bulletin-paie/pdf/", views.bulletin_paie_pdf, name="bulletin_paie_pdf"),
    path("bulletin-paie/pdf/<int:personnel_id>/", views.bulletin_paie_individuel_pdf, name="bulletin_paie_individuel_pdf"),
    path("statistiques-prestations-enseignement/", views.statistiques_prestations_enseignement, name="statistiques_prestations_enseignement"),
    path("statistiques-prestations-enseignement/pdf/", views.statistiques_prestations_enseignement_pdf, name="statistiques_prestations_enseignement_pdf"),
    path("prestations-journalieres/", views.fiche_prestations_journaliere, name="fiche_prestations_journaliere"),
    path("prestations-journalieres/pdf/", views.fiche_prestations_journaliere_pdf, name="fiche_prestations_journaliere_pdf"),
    path("etat-paie-mensuel/", views.etat_paie_mensuel, name="etat_paie_mensuel"),
    path("etat-paie-mensuel/pdf/", views.etat_paie_mensuel_pdf, name="etat_paie_mensuel_pdf"),
    path("horaires/", views.horaire_list, name="horaire_list"),
    path("horaires/nouveau/", views.horaire_create, name="horaire_create"),
    path("horaires/<int:pk>/", views.horaire_detail, name="horaire_detail"),
    path("horaires/<int:pk>/modifier/", views.horaire_update, name="horaire_update"),
    path("horaires/<int:pk>/supprimer/", views.horaire_delete, name="horaire_delete"),
    path("horaires/<int:pk>/pdf/", views.horaire_pdf, name="horaire_pdf"),
]
