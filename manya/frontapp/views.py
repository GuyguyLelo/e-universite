from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from academics.models import Section, Promotion, AnneeAcademique
from students.models import Student, Inscription
from evaluations.models import Session
from deliberations.models import Deliberation
from .dashboard_data import build_dashboard_charts, inscriptions_actives_breakdown


def _dashboard_context():
    annee_active = AnneeAcademique.get_active()
    inscriptions_breakdown = inscriptions_actives_breakdown()
    return {
        'total_etudiants': Student.objects.count(),
        'total_inscriptions': Inscription.objects.filter(statut='inscrit').count(),
        'inscriptions_premaster': inscriptions_breakdown['premaster'],
        'inscriptions_master1': inscriptions_breakdown['master1'],
        'inscriptions_master1_csi': inscriptions_breakdown['master1_csi'],
        'inscriptions_master1_rx': inscriptions_breakdown['master1_rx'],
        'total_promotions': Promotion.objects.filter(active=True).count(),
        'total_sections': Section.objects.filter(active=True).count(),
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
    """Alias post-connexion vers l'accueil."""
    return accueil(request)


@login_required
def projets_tutores_realises(request):
    """Redirection vers le module Projets tutorés réalisés."""
    return redirect('projets:accueil')
