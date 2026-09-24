from academics.models import AnneeAcademique
from config.models import Etablissement
from config.navigation import get_active_module, get_active_module_label


def ecore_navigation(request):
    module = get_active_module(request)
    return {
        "active_module": module,
        "active_module_label": get_active_module_label(module),
        "etablissement_pilote": Etablissement.get_pilote(),
    }


def ecore_annee_academique(request):
    return {
        "annee_academique_active": AnneeAcademique.get_active(),
    }