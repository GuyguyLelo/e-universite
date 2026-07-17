"""Données agrégées pour les graphiques du tableau de bord."""
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth

from academics.models import AnneeAcademique
from deliberations.models import Deliberation
from evaluations.models import Session
from students.models import Inscription


def _choice_labels(model, field_name):
    field = model._meta.get_field(field_name)
    return dict(field.choices)


_INSCRIPTION_STATUTS = _choice_labels(Inscription, 'statut')
_DELIBERATION_STATUTS = _choice_labels(Deliberation, 'statut')

PREMASTER_PROMOTION_CODE = 'PTC'


def inscriptions_actives_breakdown():
    """Effectifs Pre-Master et Master 1 parmi les inscriptions au statut « inscrit »."""
    active = Inscription.objects.filter(statut='inscrit')
    master1_csi = active.filter(classe__promotion__code='PMC').count()
    master1_rx = active.filter(classe__promotion__code='PMR').count()
    return {
        'premaster': active.filter(classe__promotion__code=PREMASTER_PROMOTION_CODE).count(),
        'master1': master1_csi + master1_rx,
        'master1_csi': master1_csi,
        'master1_rx': master1_rx,
    }


def _empty_charts():
    return {
        'inscriptions_promotion': {'labels': [], 'series': []},
        'inscriptions_statut': {'labels': [], 'series': []},
        'sessions_semestre': {'labels': [], 'series': []},
        'inscriptions_mois': {'labels': [], 'series': []},
        'deliberations_statut': {'labels': [], 'series': []},
    }


def build_dashboard_charts(annee=None):
    """Séries pour ApexCharts (année académique active par défaut)."""
    annee = annee or AnneeAcademique.get_active()
    charts = _empty_charts()
    if not annee:
        return charts

    inscriptions = Inscription.objects.filter(
        annee_academique=annee,
        classe__isnull=False,
    )

    promo_rows = list(
        inscriptions.eligibles_listes()
        .values('classe__promotion__code')
        .annotate(total=Count('id'))
        .order_by('-total', 'classe__promotion__code')[:10]
    )
    charts['inscriptions_promotion'] = {
        'labels': [row['classe__promotion__code'] or '—' for row in promo_rows],
        'series': [row['total'] for row in promo_rows],
    }

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
