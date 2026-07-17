from config.navigation import get_active_module, get_active_module_label
from academics.models import AnneeAcademique


def ecore_navigation(request):
    module = get_active_module(request)
    return {
        "active_module": module,
        "active_module_label": get_active_module_label(module),
    }


def ecore_annee_academique(request):
    return {
        "annee_academique_active": AnneeAcademique.get_active(),
    }