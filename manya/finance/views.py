from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from academics.models import AnneeAcademique, Classe, Filiere, Semestre
from students.models import Inscription

from .forms import MotifPaiementForm
from .models import ConfirmationPaiement, MotifPaiement
from .services import (
    attach_confirmation_status,
    inscription_eligible_enrollement,
    motifs_requis_inscription,
    sync_inscription_en_ordre_paiement,
)


def _annee_active_or_redirect(request):
    annee = AnneeAcademique.get_active()
    if not annee:
        messages.warning(
            request,
            'Aucune année académique active. Définissez l\'année en cours (affichée en en-tête).',
        )
    return annee


def _filieres_enrollement():
    return Filiere.objects.filter(
        code__in=MotifPaiement.FILIERES_ENROLLEMENT,
    ).order_by('code')


# ========== MOTIFS DE PAIEMENT ==========
@login_required
def motif_paiement_list(request):
    annee_active = _annee_active_or_redirect(request)
    contexte = request.GET.get('contexte') or ''
    semestre_id = request.GET.get('semestre') or ''

    motifs = MotifPaiement.objects.select_related('annee_academique', 'semestre').order_by(
        'semestre__numero',
        'contexte',
        'ordre',
        'nom',
    )
    if annee_active:
        motifs = motifs.filter(annee_academique=annee_active)
    else:
        motifs = motifs.none()

    if contexte:
        motifs = motifs.filter(contexte=contexte)
    if semestre_id:
        motifs = motifs.filter(semestre_id=semestre_id)

    semestres = Semestre.objects.filter(active=True).order_by('numero')

    return render(request, 'finance/motif_paiement_list.html', {
        'motifs': motifs,
        'annee_active': annee_active,
        'semestres': semestres,
        'semestre_id': semestre_id,
        'contexte': contexte,
        'contexte_choices': MotifPaiement.CONTEXTE_CHOICES,
        'has_filters': bool(contexte or semestre_id),
    })


@login_required
def motif_paiement_create(request):
    annee_active = _annee_active_or_redirect(request)
    if request.method == 'POST':
        form = MotifPaiementForm(request.POST, annee_active=annee_active)
        if form.is_valid():
            form.save()
            messages.success(request, 'Motif de paiement créé avec succès.')
            return redirect('finance:motif_paiement_list')
    else:
        form = MotifPaiementForm(annee_active=annee_active)
    return render(request, 'finance/motif_paiement_form.html', {
        'form': form,
        'title': 'Nouveau motif de paiement',
        'annee_active': annee_active,
    })


@login_required
def motif_paiement_detail(request, pk):
    annee_active = AnneeAcademique.get_active()
    motif = get_object_or_404(
        MotifPaiement.objects.select_related('annee_academique', 'semestre'),
        pk=pk,
    )

    inscriptions_eligibles = Inscription.objects.none()
    if annee_active and motif.annee_academique_id == annee_active.pk:
        inscriptions_eligibles = (
            Inscription.objects.filter(
                annee_academique=annee_active,
                classe__promotion__filiere__code__in=MotifPaiement.FILIERES_ENROLLEMENT,
            )
            .eligibles_listes()
            .filter(classe__isnull=False)
        )

    confirmations = ConfirmationPaiement.objects.filter(
        motif_paiement=motif,
        confirme=True,
    ).select_related(
        'inscription__etudiant',
        'inscription__classe__promotion__filiere',
        'confirme_par',
    ).order_by('-date_confirmation')[:20]

    stats = {
        'confirmes': ConfirmationPaiement.objects.filter(
            motif_paiement=motif,
            confirme=True,
        ).count(),
        'eligibles': inscriptions_eligibles.count(),
        'convoques_rattrapage': 0,
    }
    if motif.contexte == MotifPaiement.CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE:
        from .services import inscription_convoquee_rattrapage

        stats['convoques_rattrapage'] = sum(
            1
            for ins in inscriptions_eligibles.select_related('classe__promotion__filiere', 'etudiant')
            if inscription_convoquee_rattrapage(ins, motif.semestre)
        )

    return render(request, 'finance/motif_paiement_detail.html', {
        'motif': motif,
        'annee_active': annee_active,
        'stats': stats,
        'confirmations': confirmations,
        'en_ordre_url': (
            f"{reverse('finance:etudiant_en_ordre_list')}?motif={motif.pk}"
            if annee_active and motif.annee_academique_id == annee_active.pk
            else None
        ),
    })


@login_required
def motif_paiement_update(request, pk):
    annee_active = _annee_active_or_redirect(request)
    motif = get_object_or_404(MotifPaiement, pk=pk)
    if request.method == 'POST':
        form = MotifPaiementForm(request.POST, instance=motif, annee_active=annee_active)
        if form.is_valid():
            form.save()
            messages.success(request, 'Motif de paiement modifié avec succès.')
            return redirect('finance:motif_paiement_list')
    else:
        form = MotifPaiementForm(instance=motif, annee_active=annee_active)
    return render(request, 'finance/motif_paiement_form.html', {
        'form': form,
        'title': 'Modifier le motif de paiement',
        'object': motif,
        'annee_active': annee_active,
    })


@login_required
def motif_paiement_delete(request, pk):
    motif = get_object_or_404(MotifPaiement, pk=pk)
    if request.method == 'POST':
        motif.delete()
        messages.success(request, 'Motif de paiement supprimé avec succès.')
        return redirect('finance:motif_paiement_list')
    return render(request, 'finance/motif_paiement_confirm_delete.html', {'motif': motif})


# ========== ÉTUDIANTS EN ORDRE ==========
@login_required
@permission_required('students.view_inscription', raise_exception=True)
def etudiant_en_ordre_list(request):
    annee_active = _annee_active_or_redirect(request)
    q = (request.GET.get('q') or '').strip()
    filiere_id = request.GET.get('filiere') or ''
    classe_id = request.GET.get('classe') or ''
    motif_id = request.GET.get('motif') or ''

    motifs = (
        MotifPaiement.objects.filter(active=True)
        .select_related('annee_academique', 'semestre')
        .order_by('semestre__numero', 'contexte', 'ordre', 'nom')
    )
    if annee_active:
        motifs = motifs.filter(annee_academique=annee_active)
    else:
        motifs = motifs.none()

    motif_obj = None
    if motif_id:
        motif_obj = motifs.filter(pk=motif_id).first()
    elif motifs.exists():
        motif_obj = motifs.first()
        motif_id = str(motif_obj.pk)

    inscriptions = Inscription.objects.none()
    if motif_obj and annee_active:
        inscriptions = (
            Inscription.objects.filter(
                annee_academique=annee_active,
                classe__promotion__filiere__code__in=MotifPaiement.FILIERES_ENROLLEMENT,
            )
            .eligibles_listes()
            .filter(classe__isnull=False)
            .select_related(
                'etudiant',
                'classe__promotion__filiere',
                'annee_academique',
            )
            .order_by('etudiant__numero_etudiant')
        )

        if q:
            inscriptions = inscriptions.filter(
                Q(etudiant__numero_etudiant__icontains=q)
                | Q(etudiant__nom__icontains=q)
                | Q(etudiant__prenom__icontains=q)
                | Q(numero_inscription__icontains=q)
            )

        if filiere_id:
            inscriptions = inscriptions.filter(classe__promotion__filiere_id=filiere_id)

        if classe_id:
            inscriptions = inscriptions.filter(classe_id=classe_id)

    paginator = Paginator(inscriptions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    attach_confirmation_status(page_obj.object_list, motif_obj)

    filieres = _filieres_enrollement()
    classes = (
        Classe.objects.filter(promotion__filiere__code__in=MotifPaiement.FILIERES_ENROLLEMENT)
        .select_related('promotion__filiere')
        .order_by('promotion__filiere__code', 'code')
    )
    if filiere_id:
        classes = classes.filter(promotion__filiere_id=filiere_id)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    if motif_id:
        query_params['motif'] = motif_id
    has_filters = any(v for k, v in query_params.items() if k != 'motif' and v)

    return render(request, 'finance/etudiant_en_ordre_list.html', {
        'inscriptions': page_obj,
        'annee_active': annee_active,
        'q': q,
        'filiere_id': filiere_id,
        'classe_id': classe_id,
        'motif_id': motif_id,
        'motif_obj': motif_obj,
        'motifs': motifs,
        'filieres': filieres,
        'classes': classes,
        'has_filters': has_filters,
        'filter_query': query_params.urlencode(),
        'toggle_url': reverse('finance:api_etudiant_en_ordre_toggle'),
    })


@login_required
@require_POST
@permission_required('students.change_inscription', raise_exception=True)
def api_etudiant_en_ordre_toggle(request):
    inscription = get_object_or_404(
        Inscription.objects.select_related('classe__promotion__filiere'),
        pk=request.POST.get('inscription_id'),
    )
    motif = get_object_or_404(
        MotifPaiement.objects.select_related('annee_academique', 'semestre'),
        pk=request.POST.get('motif_id'),
        active=True,
    )
    confirme = request.POST.get('confirme') == '1'

    if not inscription_eligible_enrollement(inscription):
        return JsonResponse(
            {'success': False, 'message': 'L\'enrôlement concerne uniquement les filières CSI et RX.'},
            status=400,
        )

    annee_active = AnneeAcademique.get_active()
    if not annee_active or inscription.annee_academique_id != annee_active.pk:
        return JsonResponse(
            {
                'success': False,
                'message': (
                    f'L\'inscription doit être sur l\'année active '
                    f'({annee_active.code if annee_active else "non définie"}).'
                ),
            },
            status=400,
        )

    if motif.annee_academique_id != annee_active.pk:
        return JsonResponse(
            {
                'success': False,
                'message': f'Ce motif concerne l\'année {motif.annee_academique.code}.',
            },
            status=400,
        )

    confirmation, _created = ConfirmationPaiement.objects.get_or_create(
        inscription=inscription,
        motif_paiement=motif,
        defaults={'confirme': confirme, 'confirme_par': request.user},
    )
    if not _created:
        confirmation.confirme = confirme
        confirmation.confirme_par = request.user
        confirmation.save(update_fields=['confirme', 'confirme_par', 'date_confirmation', 'updated_at'])

    en_ordre_complet = sync_inscription_en_ordre_paiement(inscription)

    motifs_requis = motifs_requis_inscription(inscription, semestre=motif.semestre)
    motifs_total = motifs_requis.count()
    motifs_confirmes = ConfirmationPaiement.objects.filter(
        inscription=inscription,
        confirme=True,
        motif_paiement__in=motifs_requis,
    ).count()

    return JsonResponse({
        'success': True,
        'confirme': confirmation.confirme,
        'en_ordre_complet': en_ordre_complet,
        'motifs_complets': motifs_confirmes >= motifs_total if motifs_total else False,
        'motifs_confirmes_count': motifs_confirmes,
        'motifs_total_count': motifs_total,
    })
