"""Données agrégées pour les graphiques du tableau de bord."""
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth

from academics.models import AnneeAcademique, Departement, Faculte, Filiere
from config.models import Etablissement
from deliberations.models import Deliberation
from evaluations.models import Session
from students.models import Inscription


def _choice_labels(model, field_name):
    field = model._meta.get_field(field_name)
    return dict(field.choices)


_INSCRIPTION_STATUTS = _choice_labels(Inscription, 'statut')
_DELIBERATION_STATUTS = _choice_labels(Deliberation, 'statut')


def structure_pilote():
    """Effectifs de l'établissement pilote (UNIKIN)."""
    etab = Etablissement.get_pilote()
    if etab is None:
        return {
            'etablissement': None,
            'facultes': 0,
            'departements': 0,
            'filieres': 0,
        }
    return {
        'etablissement': etab,
        'facultes': Faculte.objects.filter(etablissement=etab, active=True).count(),
        'departements': Departement.objects.filter(faculte__etablissement=etab, active=True).count(),
        'filieres': Filiere.objects.filter(faculte__etablissement=etab, active=True).count(),
    }


def _empty_charts():
    return {
        'filieres_faculte': {'labels': [], 'series': []},
        'inscriptions_statut': {'labels': [], 'series': []},
        'sessions_semestre': {'labels': [], 'series': []},
        'inscriptions_mois': {'labels': [], 'series': []},
        'deliberations_statut': {'labels': [], 'series': []},
    }


def build_dashboard_charts(annee=None):
    """Séries pour ApexCharts (année académique active par défaut)."""
    annee = annee or AnneeAcademique.get_active()
    charts = _empty_charts()
    etab = Etablissement.get_pilote()

    filiere_qs = Filiere.objects.filter(active=True)
    if etab is not None:
        filiere_qs = filiere_qs.filter(faculte__etablissement=etab)
    faculte_rows = list(
        filiere_qs.values('faculte__code')
        .annotate(total=Count('id'))
        .order_by('-total', 'faculte__code')
    )
    charts['filieres_faculte'] = {
        'labels': [row['faculte__code'] or '—' for row in faculte_rows],
        'series': [row['total'] for row in faculte_rows],
    }

    if not annee:
        return charts

    inscriptions = Inscription.objects.filter(
        annee_academique=annee,
        classe__isnull=False,
    )

    statut_rows = list(
        inscriptions.values('statut')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    charts['inscriptions_statut'] = {
        'labels': [_INSCRIPTION_STATUTS.get(row['statut'], row['statut']) for row in statut_rows],
        'series': [row['total'] for row in statut_rows],
    }

    session_rows = list(
        Session.pour_annee(annee)
        .filter(active=True)
        .values('semestre__code')
        .annotate(
            total=Count('id'),
            en_cours=Count('id', filter=Q(deliberation_faite=False)),
            terminees=Count('id', filter=Q(deliberation_faite=True)),
        )
        .order_by('semestre__numero', 'semestre__code')
    )
    charts['sessions_semestre'] = {
        'labels': [row['semestre__code'] or '—' for row in session_rows],
        'series': [
            {'name': 'En cours', 'data': [row['en_cours'] for row in session_rows]},
            {'name': 'Délibérées', 'data': [row['terminees'] for row in session_rows]},
        ],
    }

    mois_labels = [
        'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
        'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
    ]
    mois_counts = {i: 0 for i in range(1, 13)}
    for row in inscriptions.annotate(mois=ExtractMonth('date_inscription')).values('mois').annotate(total=Count('id')):
        if row['mois']:
            mois_counts[row['mois']] = row['total']
    charts['inscriptions_mois'] = {
        'labels': mois_labels,
        'series': [mois_counts[i] for i in range(1, 13)],
    }

    delib_rows = list(
        Deliberation.objects.filter(
            Q(session__annee_academique=annee) | Q(annee_academique=annee),
        )
        .values('statut')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    charts['deliberations_statut'] = {
        'labels': [_DELIBERATION_STATUTS.get(row['statut'], row['statut']) for row in delib_rows],
        'series': [row['total'] for row in delib_rows],
    }

    return charts
