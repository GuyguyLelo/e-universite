from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import AnneeAcademique, Filiere, Semestre

from .forms import ProjetAcademiqueForm
from .models import ProjetAcademique


def _annee_active_or_redirect(request):
    annee = AnneeAcademique.get_active()
    if not annee:
        messages.warning(
            request,
            'Aucune année académique active. Définissez l\'année en cours (affichée en en-tête).',
        )
    return annee


def _filter_projets(request, queryset):
    annee_active = AnneeAcademique.get_active()
    annee_id = request.GET.get('annee') or ''
    filiere_id = request.GET.get('filiere') or ''
    semestre_id = request.GET.get('semestre') or ''
    statut = request.GET.get('statut') or ''
    q = (request.GET.get('q') or '').strip()

    if annee_id:
        queryset = queryset.filter(annee_academique_id=annee_id)
    elif annee_active:
        queryset = queryset.filter(annee_academique=annee_active)

    if filiere_id:
        queryset = queryset.filter(filiere_id=filiere_id)
    if semestre_id:
        queryset = queryset.filter(semestre_id=semestre_id)
    if statut:
        queryset = queryset.filter(statut=statut)
    if q:
        queryset = queryset.filter(
            Q(titre__icontains=q)
            | Q(resume__icontains=q)
            | Q(mots_cles__icontains=q)
            | Q(tuteur__icontains=q)
            | Q(etudiants__nom__icontains=q)
            | Q(etudiants__prenom__icontains=q)
            | Q(etudiants__numero_etudiant__icontains=q)
        ).distinct()

    return queryset, {
        'annee_active': annee_active,
        'annees': AnneeAcademique.objects.order_by('-annee_debut'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'semestres': Semestre.objects.filter(active=True).order_by('numero'),
        'annee_id': annee_id,
        'filiere_id': filiere_id,
        'semestre_id': semestre_id,
        'statut': statut,
        'q': q,
        'has_filters': bool(annee_id or filiere_id or semestre_id or statut or q),
        'statut_choices': ProjetAcademique.STATUT_CHOICES,
    }


def _projet_queryset():
    return (
        ProjetAcademique.objects.select_related(
            'annee_academique', 'filiere', 'semestre', 'element_constitutif',
        )
        .prefetch_related('etudiants')
    )


@login_required
def projets_accueil(request):
    """Point d'entrée du module."""
    return render(request, 'projets/projets_accueil.html', {
        'annee_active': AnneeAcademique.get_active(),
    })


# ========== CONSULTATION (projets finalisés) ==========

@login_required
def projet_consultation_list(request):
    projets = _projet_queryset().filter(statut=ProjetAcademique.STATUT_FINALISE)
    projets, filter_ctx = _filter_projets(request, projets)

    paginator = Paginator(projets, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'projets/projet_consultation_list.html', {
        'page_obj': page_obj,
        'projets': page_obj.object_list,
        **filter_ctx,
    })


@login_required
def projet_consultation_detail(request, pk):
    projet = get_object_or_404(
        _projet_queryset().filter(statut=ProjetAcademique.STATUT_FINALISE),
        pk=pk,
    )
    return render(request, 'projets/projet_consultation_detail.html', {
        'projet': projet,
        'annee_active': AnneeAcademique.get_active(),
    })


# ========== GESTION CRUD ==========

@login_required
@permission_required('projets.view_projetacademique', raise_exception=True)
def projet_list(request):
    annee_active = _annee_active_or_redirect(request)
    projets = _projet_queryset()
    projets, filter_ctx = _filter_projets(request, projets)

    paginator = Paginator(projets, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'projets/projet_list.html', {
        'page_obj': page_obj,
        'projets': page_obj.object_list,
        **filter_ctx,
    })


@login_required
@permission_required('projets.view_projetacademique', raise_exception=True)
def projet_detail(request, pk):
    projet = get_object_or_404(_projet_queryset(), pk=pk)
    return render(request, 'projets/projet_detail.html', {
        'projet': projet,
        'annee_active': AnneeAcademique.get_active(),
    })


@login_required
@permission_required('projets.add_projetacademique', raise_exception=True)
def projet_create(request):
    annee_active = _annee_active_or_redirect(request)
    if request.method == 'POST':
        form = ProjetAcademiqueForm(request.POST, request.FILES, annee_active=annee_active)
        if form.is_valid():
            projet = form.save()
            messages.success(request, f'Projet « {projet.titre} » créé avec succès.')
            return redirect('projets:projet_detail', pk=projet.pk)
    else:
        form = ProjetAcademiqueForm(annee_active=annee_active)
    return render(request, 'projets/projet_form.html', {
        'form': form,
        'title': 'Nouveau projet académique',
        'annee_active': annee_active,
    })


@login_required
@permission_required('projets.change_projetacademique', raise_exception=True)
def projet_update(request, pk):
    annee_active = _annee_active_or_redirect(request)
    projet = get_object_or_404(ProjetAcademique, pk=pk)
    if request.method == 'POST':
        form = ProjetAcademiqueForm(
            request.POST, request.FILES, instance=projet, annee_active=projet.annee_academique,
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Projet mis à jour avec succès.')
            return redirect('projets:projet_detail', pk=projet.pk)
    else:
        form = ProjetAcademiqueForm(instance=projet, annee_active=projet.annee_academique)
    return render(request, 'projets/projet_form.html', {
        'form': form,
        'title': 'Modifier le projet',
        'object': projet,
        'annee_active': projet.annee_academique,
    })


@login_required
@permission_required('projets.delete_projetacademique', raise_exception=True)
def projet_delete(request, pk):
    projet = get_object_or_404(ProjetAcademique, pk=pk)
    if request.method == 'POST':
        titre = projet.titre
        projet.delete()
        messages.success(request, f'Projet « {titre} » supprimé.')
        return redirect('projets:projet_list')
    return render(request, 'projets/projet_confirm_delete.html', {
        'projet': projet,
    })
