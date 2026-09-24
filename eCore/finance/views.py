from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from academics.models import AnneeAcademique, Classe, Filiere, Semestre
from students.models import Inscription

from config.pdf_entete import institution_nom

from .forms import MotifPaiementForm, PaiementForm
from .recu_paiement_pdf import build_recu_paiement_pdf
from .models import ConfirmationPaiement, MotifPaiement, Paiement
from .services import (
    attach_confirmation_status,
    frais_couvert,
    inscription_eligible_enrollement,
    motifs_requis_inscription,
    sync_inscription_en_ordre_paiement,
    synchroniser_confirmation_depuis_paiements,
    total_paye,
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
    return Filiere.objects.filter(active=True).order_by('faculte__code', 'code')


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
                classe__promotion__filiere__isnull=False,
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
                classe__promotion__filiere__isnull=False,
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
        Classe.objects.filter(promotion__filiere__isnull=False, active=True)
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
            {'success': False, 'message': 'L\'inscription doit être rattachée à une filière.'},
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


# ========== PAIEMENTS ==========
def _paiements_annee(annee):
    qs = Paiement.objects.select_related(
        'inscription__etudiant',
        'inscription__annee_academique',
        'motif_paiement__semestre',
        'enregistre_par',
    )
    if not annee:
        return qs.none()
    return qs.filter(inscription__annee_academique=annee)


@login_required
def paiement_list(request):
    annee_active = _annee_active_or_redirect(request)
    q = (request.GET.get('q') or '').strip()
    mode = request.GET.get('mode') or ''
    statut = request.GET.get('statut') or ''

    paiements = _paiements_annee(annee_active).order_by('-date_paiement', '-pk')
    if q:
        paiements = paiements.filter(
            Q(reference__icontains=q)
            | Q(reference_transaction__icontains=q)
            | Q(inscription__etudiant__numero_etudiant__icontains=q)
            | Q(inscription__etudiant__nom__icontains=q)
            | Q(inscription__etudiant__prenom__icontains=q)
        )
    if mode:
        paiements = paiements.filter(mode=mode)
    if statut:
        paiements = paiements.filter(statut=statut)

    paginator = Paginator(paiements, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'finance/paiement_list.html', {
        'paiements': page_obj,
        'annee_active': annee_active,
        'q': q,
        'mode': mode,
        'statut': statut,
        'mode_choices': Paiement.MODE_CHOICES,
        'statut_choices': Paiement.STATUT_CHOICES,
        'has_filters': bool(q or mode or statut),
        'filter_query': query_params.urlencode(),
    })


@login_required
def paiement_create(request):
    annee_active = _annee_active_or_redirect(request)
    if request.method == 'POST':
        form = PaiementForm(request.POST, annee_active=annee_active)
        if form.is_valid():
            paiement = form.save(commit=False)
            paiement.enregistre_par = request.user
            paiement.save()
            synchroniser_confirmation_depuis_paiements(
                paiement.inscription,
                paiement.motif_paiement,
                user=request.user,
            )
            messages.success(request, f'Paiement {paiement.reference} enregistré.')
            return redirect('finance:paiement_detail', pk=paiement.pk)
    else:
        form = PaiementForm(annee_active=annee_active)
    return render(request, 'finance/paiement_form.html', {
        'form': form,
        'title': 'Nouveau paiement',
        'annee_active': annee_active,
    })


@login_required
def paiement_detail(request, pk):
    paiement = get_object_or_404(
        Paiement.objects.select_related(
            'inscription__etudiant',
            'inscription__classe__promotion__filiere__faculte',
            'inscription__annee_academique',
            'motif_paiement__semestre',
            'enregistre_par',
        ),
        pk=pk,
    )
    deja_paye = total_paye(paiement.inscription, paiement.motif_paiement, devise=paiement.motif_paiement.devise)
    return render(request, 'finance/paiement_detail.html', {
        'paiement': paiement,
        'deja_paye': deja_paye,
        'frais_solde': frais_couvert(paiement.inscription, paiement.motif_paiement),
    })


def _paiement_detail_qs():
    return Paiement.objects.select_related(
        'inscription__etudiant',
        'inscription__classe__promotion__filiere__faculte',
        'inscription__classe__promotion__filiere__departement__faculte',
        'inscription__annee_academique',
        'motif_paiement',
        'enregistre_par',
    )


@login_required
def paiement_recu_pdf(request, pk):
    paiement = get_object_or_404(_paiement_detail_qs(), pk=pk)
    pdf = build_recu_paiement_pdf(paiement)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="recu-{paiement.reference}.pdf"'
    return response


def recu_public(request, reference):
    paiement = get_object_or_404(
        _paiement_detail_qs(),
        reference=reference,
    )
    return render(request, 'finance/recu_public.html', {
        'paiement': paiement,
        'etudiant': paiement.inscription.etudiant,
        'universite': institution_nom(),
    })


@login_required
def paiement_update(request, pk):
    annee_active = _annee_active_or_redirect(request)
    paiement = get_object_or_404(Paiement, pk=pk)
    ancien = (paiement.inscription_id, paiement.motif_paiement_id)
    if request.method == 'POST':
        form = PaiementForm(request.POST, instance=paiement, annee_active=annee_active)
        if form.is_valid():
            paiement = form.save(commit=False)
            if not paiement.enregistre_par_id:
                paiement.enregistre_par = request.user
            paiement.save()
            synchroniser_confirmation_depuis_paiements(
                paiement.inscription,
                paiement.motif_paiement,
                user=request.user,
            )
            if ancien != (paiement.inscription_id, paiement.motif_paiement_id):
                from students.models import Inscription
                ancienne_inscription = Inscription.objects.filter(pk=ancien[0]).first()
                ancien_motif = MotifPaiement.objects.filter(pk=ancien[1]).first()
                if ancienne_inscription and ancien_motif:
                    synchroniser_confirmation_depuis_paiements(
                        ancienne_inscription,
                        ancien_motif,
                        user=request.user,
                    )
            messages.success(request, f'Paiement {paiement.reference} modifié.')
            return redirect('finance:paiement_detail', pk=paiement.pk)
    else:
        form = PaiementForm(instance=paiement, annee_active=annee_active)
    return render(request, 'finance/paiement_form.html', {
        'form': form,
        'title': 'Modifier le paiement',
        'object': paiement,
        'annee_active': annee_active,
    })


@login_required
def paiement_delete(request, pk):
    paiement = get_object_or_404(
        Paiement.objects.select_related('inscription', 'motif_paiement'),
        pk=pk,
    )
    if request.method == 'POST':
        inscription = paiement.inscription
        motif = paiement.motif_paiement
        reference = paiement.reference
        paiement.delete()
        synchroniser_confirmation_depuis_paiements(inscription, motif, user=request.user)
        messages.success(request, f'Paiement {reference} supprimé.')
        return redirect('finance:paiement_list')
    return render(request, 'finance/paiement_confirm_delete.html', {'paiement': paiement})


