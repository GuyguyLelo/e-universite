"""
Vues pour l'application deliberations
"""
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from .models import ParametresLMD, Deliberation, DecisionJury
from .forms import ParametresLMDForm, DeliberationForm, DecisionJuryForm, DetteListFilterForm, JuryMemberAddForm
from .access import (
    deliberations_for_user,
    user_can_access_deliberation,
    user_can_edit_decision,
    user_can_manage_deliberations,
    ensure_jury_group,
    JURY_GROUP_NAME,
)
from .dettes_services import lister_passages_avec_dettes, SEUIL_VALIDATION_EC
from .services import DeliberationEngine, mention_code_depuis_moyenne
from .annual_services import DeliberationAnnuelleEngine, peut_deliberer_annuelle, DeliberationAnnuelleError
from .cycle_services import DeliberationCycleMasterEngine, peut_deliberer_cycle_master, DeliberationCycleMasterError
from evaluations.session_workflow import peut_deliberer
from students.models import Inscription
from academics.models import AnneeAcademique
from academics.utils import NO_ACTIVE_ANNEE_ERROR
from documents.services import enregistrer_grille_notes_pdf


def _get_deliberation_or_403(request, pk):
    deliberation = get_object_or_404(Deliberation, pk=pk)
    if not user_can_access_deliberation(request.user, deliberation):
        raise PermissionDenied
    return deliberation


def deliberation_access_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, pk, *args, **kwargs):
        _get_deliberation_or_403(request, pk)
        return view_func(request, pk, *args, **kwargs)
    return wrapper


def _inscription_etudiant(deliberation, etudiant):
    qs = Inscription.objects.filter(
        etudiant=etudiant,
        classe__promotion=deliberation.promotion,
    ).eligibles_listes().select_related('classe')
    if deliberation.type_deliberation in (
        Deliberation.TYPE_ANNUELLE,
        Deliberation.TYPE_CYCLE_MASTER,
    ):
        qs = qs.filter(annee_academique=deliberation.annee_academique)
    return qs.first()


def _assigner_rangs(deliberation):
    decisions = list(
        DecisionJury.objects.filter(deliberation=deliberation)
        .order_by('-moyenne_semestre', 'etudiant__numero_etudiant')
    )
    for rang, decision in enumerate(decisions, start=1):
        if decision.rang != rang:
            decision.rang = rang
            decision.save(update_fields=['rang', 'updated_at'])


def _calculer_deliberation_semestrielle(request, deliberation):
    session = deliberation.session
    engine = DeliberationEngine(session, deliberation.promotion)
    resultats = engine.traiter_tous_etudiants()

    decisions_crees = 0
    for resultat in resultats:
        inscription = _inscription_etudiant(deliberation, resultat['etudiant'])
        if inscription:
            _, created = DecisionJury.objects.update_or_create(
                deliberation=deliberation,
                etudiant=resultat['etudiant'],
                defaults={
                    'inscription': inscription,
                    'moyenne_semestre': resultat['moyenne_semestre'],
                    'credits_obtenus': resultat['credits_obtenus'],
                    'credits_totaux': resultat['credits_totaux'],
                    'decision': resultat['decision'],
                    'mention': mention_code_depuis_moyenne(resultat['moyenne_semestre']),
                    'moyenne_semestre1': None,
                    'moyenne_semestre2': None,
                    'credits_semestre1': None,
                    'credits_semestre2': None,
                },
            )
            if created:
                decisions_crees += 1

    _assigner_rangs(deliberation)

    session.deliberation_faite = True
    session.verrouillee = True
    session.save(update_fields=['deliberation_faite', 'verrouillee', 'updated_at'])

    deliberation.statut = 'terminee'
    deliberation.save(update_fields=['statut', 'updated_at'])

    annee = AnneeAcademique.get_active()
    if annee:
        try:
            enregistrer_grille_notes_pdf(
                session.semestre,
                deliberation.promotion.filiere,
                deliberation.promotion,
                annee,
                session,
                deliberation=deliberation,
                genere_par=request.user,
            )
            return decisions_crees, True
        except Exception:
            return decisions_crees, False
    return decisions_crees, None


def _calculer_deliberation_annuelle(request, deliberation):
    engine = DeliberationAnnuelleEngine(
        deliberation.promotion,
        deliberation.annee_academique,
        deliberation.semestre1,
        deliberation.semestre2,
    )
    resultats = engine.traiter_tous_etudiants()

    decisions_crees = 0
    for resultat in resultats:
        inscription = _inscription_etudiant(deliberation, resultat['etudiant'])
        if inscription:
            _, created = DecisionJury.objects.update_or_create(
                deliberation=deliberation,
                etudiant=resultat['etudiant'],
                defaults={
                    'inscription': inscription,
                    'moyenne_semestre': resultat['moyenne_annuelle'],
                    'moyenne_semestre1': resultat['moyenne_semestre1'],
                    'moyenne_semestre2': resultat['moyenne_semestre2'],
                    'credits_semestre1': resultat['credits_semestre1'],
                    'credits_semestre2': resultat['credits_semestre2'],
                    'credits_obtenus': resultat['credits_obtenus'],
                    'credits_totaux': resultat['credits_totaux'],
                    'decision': resultat['decision'],
                    'mention': resultat['mention'],
                },
            )
            if created:
                decisions_crees += 1

    _assigner_rangs(deliberation)
    deliberation.statut = 'terminee'
    deliberation.save(update_fields=['statut', 'updated_at'])
    return decisions_crees


def _calculer_deliberation_cycle_master(request, deliberation):
    engine = DeliberationCycleMasterEngine(
        deliberation.promotion,
        deliberation.annee_academique_m1,
        deliberation.annee_academique,
    )
    resultats = engine.traiter_tous_etudiants()

    decisions_crees = 0
    for resultat in resultats:
        inscription = _inscription_etudiant(deliberation, resultat['etudiant'])
        if inscription:
            _, created = DecisionJury.objects.update_or_create(
                deliberation=deliberation,
                etudiant=resultat['etudiant'],
                defaults={
                    'inscription': inscription,
                    'moyenne_semestre': resultat['moyenne_cycle'],
                    'moyenne_semestre1': resultat['moyenne_m1'],
                    'moyenne_semestre2': resultat['moyenne_m2'],
                    'credits_semestre1': resultat['credits_m1'],
                    'credits_semestre2': resultat['credits_m2'],
                    'credits_obtenus': resultat['credits_obtenus'],
                    'credits_totaux': resultat['credits_totaux'],
                    'decision': resultat['decision'],
                    'mention': resultat['mention'],
                },
            )
            if created:
                decisions_crees += 1

    _assigner_rangs(deliberation)
    deliberation.statut = 'terminee'
    deliberation.save(update_fields=['statut', 'updated_at'])
    return decisions_crees


# ========== PARAMETRES LMD ==========
@login_required
@permission_required('deliberations.view_parametreslmd', raise_exception=True)
def parametres_lmd_list(request):
    parametres = ParametresLMD.objects.select_related('promotion').all()
    return render(request, 'deliberations/parametres_lmd_list.html', {'parametres': parametres})


@login_required
@permission_required('deliberations.add_parametreslmd', raise_exception=True)
def parametres_lmd_create(request):
    if request.method == 'POST':
        form = ParametresLMDForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres LMD créés avec succès!')
            return redirect('deliberations:parametres_lmd_list')
    else:
        form = ParametresLMDForm()
    return render(request, 'deliberations/parametres_lmd_form.html', {'form': form, 'title': 'Nouveaux Paramètres LMD'})


@login_required
@permission_required('deliberations.change_parametreslmd', raise_exception=True)
def parametres_lmd_update(request, pk):
    parametres = get_object_or_404(ParametresLMD, pk=pk)
    if request.method == 'POST':
        form = ParametresLMDForm(request.POST, instance=parametres)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres LMD modifiés avec succès!')
            return redirect('deliberations:parametres_lmd_list')
    else:
        form = ParametresLMDForm(instance=parametres)
    return render(request, 'deliberations/parametres_lmd_form.html', {'form': form, 'title': 'Modifier Paramètres LMD', 'object': parametres})


# ========== DELIBERATIONS ==========
@login_required
@permission_required('deliberations.view_deliberation', raise_exception=True)
def deliberation_list(request):
    deliberations = (
        deliberations_for_user(request.user)
        .select_related(
            'session', 'session__semestre', 'promotion', 'president_jury',
            'annee_academique', 'annee_academique_m1', 'semestre1', 'semestre2',
        )
        .order_by('-date_deliberation')
    )
    paginator = Paginator(deliberations, 10)
    page = request.GET.get('page')
    deliberations = paginator.get_page(page)
    return render(request, 'deliberations/deliberation_list.html', {
        'deliberations': deliberations,
        'can_manage_deliberations': user_can_manage_deliberations(request.user),
    })


@login_required
@permission_required('deliberations.add_deliberation', raise_exception=True)
def deliberation_create(request):
    if request.method == 'POST':
        form = DeliberationForm(request.POST)
        if form.is_valid():
            deliberation = form.save(commit=False)
            if not deliberation.president_jury:
                deliberation.president_jury = request.user
            deliberation.save()
            form.save_m2m()
            messages.success(request, 'Délibération créée avec succès!')
            return redirect('deliberations:deliberation_list')
    else:
        form = DeliberationForm()
        annee = AnneeAcademique.get_active()
        if annee:
            form.fields['annee_academique'].initial = annee.pk
    return render(request, 'deliberations/deliberation_form.html', {'form': form, 'title': 'Nouvelle Délibération'})


@login_required
@permission_required('deliberations.change_deliberation', raise_exception=True)
def deliberation_update(request, pk):
    deliberation = _get_deliberation_or_403(request, pk)
    if request.method == 'POST':
        form = DeliberationForm(request.POST, instance=deliberation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Délibération modifiée avec succès!')
            return redirect('deliberations:deliberation_list')
    else:
        form = DeliberationForm(instance=deliberation)
    return render(request, 'deliberations/deliberation_form.html', {'form': form, 'title': 'Modifier Délibération', 'object': deliberation})


@deliberation_access_required
@permission_required('deliberations.view_deliberation', raise_exception=True)
def deliberation_detail(request, pk):
    deliberation = get_object_or_404(
        Deliberation.objects.select_related(
            'session', 'semestre1', 'semestre2', 'annee_academique', 'annee_academique_m1',
            'promotion', 'president_jury',
        ).prefetch_related('membres_jury'),
        pk=pk,
    )
    decisions = DecisionJury.objects.filter(deliberation=deliberation).order_by('rang', 'etudiant')
    return render(request, 'deliberations/deliberation_detail.html', {
        'deliberation': deliberation,
        'decisions': decisions,
        'composition_bureau': deliberation.composition_bureau,
        'est_agregee': deliberation.est_agregee,
        'est_cycle_master': deliberation.type_deliberation == Deliberation.TYPE_CYCLE_MASTER,
        'can_manage_deliberations': user_can_manage_deliberations(request.user),
        'can_edit_decisions': user_can_edit_decision(request.user, deliberation),
    })


@deliberation_access_required
@permission_required('deliberations.change_deliberation', raise_exception=True)
def deliberation_calculer(request, pk):
    """Calcule les notes et décisions pour une délibération semestrielle ou annuelle."""
    deliberation = get_object_or_404(
        Deliberation.objects.select_related(
            'session', 'promotion', 'annee_academique', 'annee_academique_m1',
            'semestre1', 'semestre2',
        ),
        pk=pk,
    )

    if deliberation.type_deliberation == Deliberation.TYPE_CYCLE_MASTER:
        ok, message = peut_deliberer_cycle_master(
            deliberation.promotion,
            deliberation.annee_academique_m1,
            deliberation.annee_academique,
        )
        if deliberation.statut == 'terminee':
            ok, message = False, 'Cette délibération cycle Master est déjà terminée.'
    elif deliberation.type_deliberation == Deliberation.TYPE_ANNUELLE:
        ok, message = peut_deliberer_annuelle(
            deliberation.promotion,
            deliberation.annee_academique,
            deliberation.semestre1,
            deliberation.semestre2,
        )
        if deliberation.statut == 'terminee':
            ok, message = False, 'Cette délibération annuelle est déjà terminée.'
    else:
        ok, message = peut_deliberer(deliberation.session, deliberation.promotion)

    if request.method == 'POST':
        if not ok:
            messages.error(request, message)
            return redirect('deliberations:deliberation_calculer', pk=deliberation.pk)

        if deliberation.type_deliberation == Deliberation.TYPE_CYCLE_MASTER:
            try:
                decisions_crees = _calculer_deliberation_cycle_master(request, deliberation)
            except DeliberationCycleMasterError as exc:
                messages.error(request, str(exc))
                return redirect('deliberations:deliberation_calculer', pk=deliberation.pk)
            messages.success(
                request,
                f'Délibération cycle Master effectuée — {decisions_crees} décision(s) créée(s).',
            )
        elif deliberation.type_deliberation == Deliberation.TYPE_ANNUELLE:
            try:
                decisions_crees = _calculer_deliberation_annuelle(request, deliberation)
            except DeliberationAnnuelleError as exc:
                messages.error(request, str(exc))
                return redirect('deliberations:deliberation_calculer', pk=deliberation.pk)
            messages.success(
                request,
                f'Délibération annuelle effectuée — {decisions_crees} décision(s) créée(s).',
            )
        else:
            decisions_crees, grille_ok = _calculer_deliberation_semestrielle(request, deliberation)
            if grille_ok is True:
                messages.success(
                    request,
                    f'Calculs effectués avec succès ! {decisions_crees} décision(s) créée(s). '
                    'Grille de notes enregistrée.',
                )
            elif grille_ok is False:
                messages.warning(
                    request,
                    f'Calculs effectués ({decisions_crees} décision(s) créée(s)), '
                    "mais l'enregistrement de la grille PDF a échoué.",
                )
            else:
                messages.success(
                    request,
                    f'Calculs effectués avec succès ! {decisions_crees} décision(s) créée(s). '
                    f'{NO_ACTIVE_ANNEE_ERROR} — grille PDF non enregistrée.',
                )
        return redirect('deliberations:deliberation_detail', pk=deliberation.pk)

    return render(request, 'deliberations/deliberation_calculer.html', {
        'deliberation': deliberation,
        'peut_calculer': ok,
        'message_blocage': message,
        'est_agregee': deliberation.est_agregee,
        'est_cycle_master': deliberation.type_deliberation == Deliberation.TYPE_CYCLE_MASTER,
    })


# ========== DECISIONS JURY ==========
@login_required
def decision_jury_update(request, pk):
    decision = get_object_or_404(DecisionJury.objects.select_related('deliberation'), pk=pk)
    if not user_can_edit_decision(request.user, decision.deliberation):
        raise PermissionDenied
    if request.method == 'POST':
        form = DecisionJuryForm(request.POST, instance=decision)
        if form.is_valid():
            form.save()
            messages.success(request, 'Décision modifiée avec succès!')
            return redirect('deliberations:deliberation_detail', pk=decision.deliberation.pk)
    else:
        form = DecisionJuryForm(instance=decision)
    return render(request, 'deliberations/decision_jury_form.html', {'form': form, 'title': 'Modifier Décision', 'object': decision})


# ========== GESTION DU JURY ==========
@login_required
@permission_required('deliberations.change_deliberation', raise_exception=True)
def jury_gestion(request):
    """Comptes du groupe Jury et composition des jurys par délibération."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    group = ensure_jury_group()
    membres_qs = group.user_set.filter(is_active=True).order_by('last_name', 'first_name', 'username')
    membre_ids = list(membres_qs.values_list('pk', flat=True))

    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        if action == 'add':
            form = JuryMemberAddForm(request.POST, exclude_ids=membre_ids)
            if form.is_valid():
                user = form.cleaned_data['utilisateur']
                group.user_set.add(user)
                messages.success(
                    request,
                    f'{user.get_full_name() or user.username} ajouté au groupe {JURY_GROUP_NAME}.',
                )
            else:
                messages.error(request, 'Sélectionnez un utilisateur valide.')
        elif action == 'remove' and user_id:
            user = get_object_or_404(User, pk=user_id)
            group.user_set.remove(user)
            messages.success(
                request,
                f'{user.get_full_name() or user.username} retiré du groupe {JURY_GROUP_NAME}.',
            )
        return redirect('deliberations:jury_gestion')

    add_form = JuryMemberAddForm(exclude_ids=membre_ids)
    deliberations = (
        Deliberation.objects.select_related(
            'session', 'promotion', 'president_jury', 'annee_academique', 'semestre1', 'semestre2',
        )
        .prefetch_related('membres_jury')
        .order_by('-date_deliberation')
    )
    return render(request, 'deliberations/jury_gestion.html', {
        'jury_group': group,
        'membres': membres_qs,
        'add_form': add_form,
        'deliberations': deliberations,
    })


# ========== DETTES ACADÉMIQUES ==========
@login_required
@permission_required('deliberations.change_deliberation', raise_exception=True)
def dette_list(request):
    """Passage en promotion supérieure avec EC non validés de la promotion précédente."""
    annee = AnneeAcademique.get_active()
    filter_form = DetteListFilterForm(request.GET or None, annee=annee)
    lignes = []
    stats = {'etudiants': 0, 'ecs': 0}

    if not annee:
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
    elif filter_form.is_valid():
        lignes = lister_passages_avec_dettes(
            annee_academique=annee,
            filiere=filter_form.cleaned_data.get('filiere'),
            promotion=filter_form.cleaned_data.get('promotion'),
            classe=filter_form.cleaned_data.get('classe'),
            q=filter_form.cleaned_data.get('q'),
        )
        stats['etudiants'] = len(lignes)
        stats['ecs'] = sum(ligne['nb_dettes'] for ligne in lignes)

    filter_query = request.GET.copy()
    filter_query.pop('page', None)
    has_filters = any(v for k, v in filter_query.items() if v)

    paginator = Paginator(lignes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'deliberations/dette_list.html', {
        'annee': annee,
        'filter_form': filter_form,
        'lignes': page_obj,
        'stats': stats,
        'seuil_validation': SEUIL_VALIDATION_EC,
        'has_filters': has_filters,
        'filter_query': filter_query.urlencode(),
    })
