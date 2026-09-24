from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from academics.models import AnneeAcademique
from evaluations.models import Session
from deliberations.models import Deliberation
from students.models import Inscription, Student
from .dashboard_data import build_dashboard_charts, structure_pilote


def _dashboard_context():
    annee_active = AnneeAcademique.get_active()
    structure = structure_pilote()
    return {
        'total_etudiants': Student.objects.count(),
        'total_inscriptions': Inscription.objects.filter(statut='inscrit').count(),
        'total_facultes': structure['facultes'],
        'total_departements': structure['departements'],
        'total_filieres': structure['filieres'],
        'annee_active': annee_active,
        'sessions_actives': Session.pour_annee(annee_active).filter(
            active=True, deliberation_faite=False,
        ).count(),
        'deliberations_recentes': Deliberation.objects.filter(statut='terminee').order_by('-date_deliberation')[:5],
        'dashboard_charts': build_dashboard_charts(annee_active),
    }


@login_required
def accueil(request):
    """Page d'accueil — sélection des fonctionnalités."""
    return render(request, 'frontapp/accueil.html', _dashboard_context())


@login_required
def dashboard(request):
    """Tableau de bord — statistiques et indicateurs."""
    return render(request, 'frontapp/dashboard.html', _dashboard_context())


@login_required
def home(request):
    """Alias post-connexion vers l'accueil, ou l'espace étudiant."""
    if not request.user.is_staff and getattr(request.user, "student_profile", None):
        return redirect("students:mon_espace")
    return accueil(request)


@login_required
def projets_tutores_realises(request):
    """Redirection vers le module Projets tutorés réalisés."""
    return redirect('projets:accueil')
