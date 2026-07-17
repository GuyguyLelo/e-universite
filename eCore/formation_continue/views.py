from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .brevet_pdf import generer_brevet_pdf
from .forms import (
    BrevetForm,
    FormateurForm,
    InscriptionForm,
    ModuleTICForm,
    OffreModuleForm,
    PresenceForm,
    SeminaristeForm,
    SessionFormationForm,
)
from .models import (
    Brevet,
    Formateur,
    Inscription,
    ModuleTIC,
    OffreModule,
    Presence,
    Seminariste,
    SessionFormation,
)
from .services import cloturer_session, resume_session_pour_cloture


@login_required
def accueil(request):
    return render(request, 'formation_continue/accueil.html', {
        'nb_seminaristes': Seminariste.objects.filter(active=True).count(),
        'nb_sessions': SessionFormation.objects.filter(active=True).count(),
        'nb_modules': ModuleTIC.objects.filter(active=True).count(),
        'nb_brevets': Brevet.objects.count(),
        'sessions_recentes': SessionFormation.objects.order_by('-annee', 'numero')[:4],
    })


# ---------- Sessions ----------

@login_required
@permission_required('formation_continue.view_sessionformation', raise_exception=True)
def session_list(request):
    qs = SessionFormation.objects.annotate(nb_inscrits=Count('inscriptions'))
    annee = request.GET.get('annee') or ''
    q = (request.GET.get('q') or '').strip()
    if annee:
        qs = qs.filter(annee=annee)
    if q:
        qs = qs.filter(Q(libelle__icontains=q) | Q(numero__icontains=q))
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    annees = (
        SessionFormation.objects.order_by('-annee')
        .values_list('annee', flat=True)
        .distinct()
    )
    return render(request, 'formation_continue/session_list.html', {
        'page_obj': page_obj,
        'sessions': page_obj.object_list,
        'annee': annee,
        'annees': annees,
        'q': q,
    })


@login_required
@permission_required('formation_continue.add_sessionformation', raise_exception=True)
def session_create(request):
    form = SessionFormationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Session « {obj} » créée.')
        return redirect('formation_continue:session_list')
    return render(request, 'formation_continue/session_form.html', {
        'form': form,
        'title': 'Nouvelle session',
    })


@login_required
@permission_required('formation_continue.change_sessionformation', raise_exception=True)
def session_update(request, pk):
    obj = get_object_or_404(SessionFormation, pk=pk)
    if obj.cloturee:
        messages.warning(request, 'Cette session est clôturée et ne peut plus être modifiée.')
        return redirect('formation_continue:cloture_session_detail', pk=obj.pk)
    form = SessionFormationForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Session mise à jour.')
        return redirect('formation_continue:session_list')
    return render(request, 'formation_continue/session_form.html', {
        'form': form,
        'title': f'Modifier — {obj}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_sessionformation', raise_exception=True)
def session_delete(request, pk):
    obj = get_object_or_404(SessionFormation, pk=pk)
    if obj.cloturee:
        messages.error(request, 'Impossible de supprimer une session clôturée.')
        return redirect('formation_continue:session_list')
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Session supprimée.')
        return redirect('formation_continue:session_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer la session',
        'cancel_url': 'formation_continue:session_list',
    })


# ---------- Clôture de session ----------

@login_required
@permission_required('formation_continue.view_sessionformation', raise_exception=True)
def cloture_session_list(request):
    qs = (
        SessionFormation.objects
        .annotate(
            nb_inscrits=Count('inscriptions'),
            nb_brevets=Count('brevets', distinct=True),
        )
        .order_by('cloturee', '-annee', 'numero')
    )
    filtre = request.GET.get('filtre') or 'ouvertes'
    if filtre == 'cloturees':
        qs = qs.filter(cloturee=True)
    elif filtre == 'toutes':
        pass
    else:
        filtre = 'ouvertes'
        qs = qs.filter(cloturee=False)

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/cloture_session_list.html', {
        'page_obj': page_obj,
        'sessions': page_obj.object_list,
        'filtre': filtre,
    })


@login_required
@permission_required('formation_continue.view_sessionformation', raise_exception=True)
def cloture_session_detail(request, pk):
    session = get_object_or_404(SessionFormation, pk=pk)
    resume = resume_session_pour_cloture(session)
    can_cloturer = (
        session.peut_etre_cloturee()
        and (
            request.user.has_perm('formation_continue.cloturer_sessionformation')
            or request.user.has_perm('formation_continue.change_sessionformation')
            or request.user.is_superuser
        )
    )

    if request.method == 'POST' and 'cloturer' in request.POST:
        if not can_cloturer:
            messages.error(request, 'Vous n’avez pas l’autorisation de clôturer cette session.')
            return redirect('formation_continue:cloture_session_detail', pk=pk)
        try:
            cloturer_session(
                session,
                request.user,
                observations=request.POST.get('observations_cloture', ''),
            )
            messages.success(
                request,
                f'Session « {session} » clôturée. Les inscriptions actives sont marquées terminées.',
            )
        except ValueError as exc:
            messages.warning(request, str(exc))
        return redirect('formation_continue:cloture_session_detail', pk=pk)

    return render(request, 'formation_continue/cloture_session_detail.html', {
        'session': session,
        'resume': resume,
        'can_cloturer': can_cloturer,
    })


# ---------- Modules ----------

@login_required
@permission_required('formation_continue.view_moduletic', raise_exception=True)
def module_list(request):
    qs = ModuleTIC.objects.all()
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(intitule__icontains=q))
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/module_list.html', {
        'page_obj': page_obj,
        'modules': page_obj.object_list,
        'q': q,
    })


@login_required
@permission_required('formation_continue.add_moduletic', raise_exception=True)
def module_create(request):
    form = ModuleTICForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Module « {obj} » créé.')
        return redirect('formation_continue:module_list')
    return render(request, 'formation_continue/module_form.html', {
        'form': form,
        'title': 'Nouveau module TIC',
    })


@login_required
@permission_required('formation_continue.change_moduletic', raise_exception=True)
def module_update(request, pk):
    obj = get_object_or_404(ModuleTIC, pk=pk)
    form = ModuleTICForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Module mis à jour.')
        return redirect('formation_continue:module_list')
    return render(request, 'formation_continue/module_form.html', {
        'form': form,
        'title': f'Modifier — {obj.code}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_moduletic', raise_exception=True)
def module_delete(request, pk):
    obj = get_object_or_404(ModuleTIC, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Module supprimé.')
        return redirect('formation_continue:module_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer le module',
        'cancel_url': 'formation_continue:module_list',
    })


# ---------- Formateurs ----------

@login_required
@permission_required('formation_continue.view_formateur', raise_exception=True)
def formateur_list(request):
    qs = Formateur.objects.all()
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(specialite__icontains=q)
        )
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/formateur_list.html', {
        'page_obj': page_obj,
        'formateurs': page_obj.object_list,
        'q': q,
    })


@login_required
@permission_required('formation_continue.add_formateur', raise_exception=True)
def formateur_create(request):
    form = FormateurForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Formateur « {obj} » enregistré.')
        return redirect('formation_continue:formateur_list')
    return render(request, 'formation_continue/formateur_form.html', {
        'form': form,
        'title': 'Nouveau formateur',
    })


@login_required
@permission_required('formation_continue.change_formateur', raise_exception=True)
def formateur_update(request, pk):
    obj = get_object_or_404(Formateur, pk=pk)
    form = FormateurForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Formateur mis à jour.')
        return redirect('formation_continue:formateur_list')
    return render(request, 'formation_continue/formateur_form.html', {
        'form': form,
        'title': f'Modifier — {obj}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_formateur', raise_exception=True)
def formateur_delete(request, pk):
    obj = get_object_or_404(Formateur, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Formateur supprimé.')
        return redirect('formation_continue:formateur_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer le formateur',
        'cancel_url': 'formation_continue:formateur_list',
    })


# ---------- Séminaristes ----------

@login_required
@permission_required('formation_continue.view_seminariste', raise_exception=True)
def seminariste_list(request):
    qs = Seminariste.objects.all()
    type_p = request.GET.get('type') or ''
    q = (request.GET.get('q') or '').strip()
    if type_p:
        qs = qs.filter(type_participant=type_p)
    if q:
        qs = qs.filter(
            Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(matricule__icontains=q)
            | Q(organisation__icontains=q)
        )
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/seminariste_list.html', {
        'page_obj': page_obj,
        'seminaristes': page_obj.object_list,
        'type': type_p,
        'type_choices': Seminariste.TYPE_CHOICES,
        'q': q,
    })


@login_required
@permission_required('formation_continue.add_seminariste', raise_exception=True)
def seminariste_create(request):
    form = SeminaristeForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Séminariste « {obj} » enregistré.')
        return redirect('formation_continue:seminariste_detail', pk=obj.pk)
    return render(request, 'formation_continue/seminariste_form.html', {
        'form': form,
        'title': 'Nouveau séminariste',
    })


@login_required
@permission_required('formation_continue.view_seminariste', raise_exception=True)
def seminariste_detail(request, pk):
    obj = get_object_or_404(Seminariste, pk=pk)
    inscriptions = (
        obj.inscriptions.select_related('session')
        .prefetch_related('modules__module')
        .order_by('-date_inscription')
    )
    brevets = obj.brevets.select_related('session').order_by('-date_delivrance')
    return render(request, 'formation_continue/seminariste_detail.html', {
        'seminariste': obj,
        'inscriptions': inscriptions,
        'brevets': brevets,
    })


@login_required
@permission_required('formation_continue.change_seminariste', raise_exception=True)
def seminariste_update(request, pk):
    obj = get_object_or_404(Seminariste, pk=pk)
    form = SeminaristeForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Séminariste mis à jour.')
        return redirect('formation_continue:seminariste_detail', pk=obj.pk)
    return render(request, 'formation_continue/seminariste_form.html', {
        'form': form,
        'title': f'Modifier — {obj}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_seminariste', raise_exception=True)
def seminariste_delete(request, pk):
    obj = get_object_or_404(Seminariste, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Séminariste supprimé.')
        return redirect('formation_continue:seminariste_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer le séminariste',
        'cancel_url': 'formation_continue:seminariste_list',
    })


# ---------- Offres de modules ----------

@login_required
@permission_required('formation_continue.view_offremodule', raise_exception=True)
def offre_list(request):
    qs = OffreModule.objects.select_related('session', 'module', 'formateur')
    session_id = request.GET.get('session') or ''
    if session_id:
        qs = qs.filter(session_id=session_id)
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/offre_list.html', {
        'page_obj': page_obj,
        'offres': page_obj.object_list,
        'sessions': SessionFormation.objects.filter(active=True),
        'session_id': session_id,
    })


@login_required
@permission_required('formation_continue.add_offremodule', raise_exception=True)
def offre_create(request):
    form = OffreModuleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Offre « {obj.module} » enregistrée.')
        return redirect('formation_continue:offre_list')
    return render(request, 'formation_continue/offre_form.html', {
        'form': form,
        'title': 'Affecter un module à une session',
    })


@login_required
@permission_required('formation_continue.change_offremodule', raise_exception=True)
def offre_update(request, pk):
    obj = get_object_or_404(OffreModule, pk=pk)
    form = OffreModuleForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Offre mise à jour.')
        return redirect('formation_continue:offre_list')
    return render(request, 'formation_continue/offre_form.html', {
        'form': form,
        'title': f'Modifier — {obj.module}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_offremodule', raise_exception=True)
def offre_delete(request, pk):
    obj = get_object_or_404(OffreModule, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Offre supprimée.')
        return redirect('formation_continue:offre_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer l’offre de module',
        'cancel_url': 'formation_continue:offre_list',
    })


# ---------- Inscriptions ----------

@login_required
@permission_required('formation_continue.view_inscription', raise_exception=True)
def inscription_list(request):
    qs = Inscription.objects.select_related('seminariste', 'session').prefetch_related('modules')
    session_id = request.GET.get('session') or ''
    statut = request.GET.get('statut') or ''
    q = (request.GET.get('q') or '').strip()
    if session_id:
        qs = qs.filter(session_id=session_id)
    if statut:
        qs = qs.filter(statut=statut)
    if q:
        qs = qs.filter(
            Q(seminariste__nom__icontains=q) | Q(seminariste__prenom__icontains=q)
        )
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/inscription_list.html', {
        'page_obj': page_obj,
        'inscriptions': page_obj.object_list,
        'sessions': SessionFormation.objects.filter(active=True),
        'session_id': session_id,
        'statut': statut,
        'statut_choices': Inscription.STATUT_CHOICES,
        'q': q,
    })


@login_required
@permission_required('formation_continue.add_inscription', raise_exception=True)
def inscription_create(request):
    form = InscriptionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Inscription de « {obj.seminariste} » enregistrée.')
        return redirect('formation_continue:inscription_list')
    return render(request, 'formation_continue/inscription_form.html', {
        'form': form,
        'title': 'Nouvelle inscription',
    })


@login_required
@permission_required('formation_continue.change_inscription', raise_exception=True)
def inscription_update(request, pk):
    obj = get_object_or_404(Inscription, pk=pk)
    form = InscriptionForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Inscription mise à jour.')
        return redirect('formation_continue:inscription_list')
    return render(request, 'formation_continue/inscription_form.html', {
        'form': form,
        'title': f'Modifier — {obj.seminariste}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_inscription', raise_exception=True)
def inscription_delete(request, pk):
    obj = get_object_or_404(Inscription, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Inscription supprimée.')
        return redirect('formation_continue:inscription_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer l’inscription',
        'cancel_url': 'formation_continue:inscription_list',
    })


# ---------- Présences ----------

@login_required
@permission_required('formation_continue.view_presence', raise_exception=True)
def presence_list(request):
    qs = Presence.objects.select_related(
        'inscription__seminariste',
        'offre_module__module',
        'offre_module__session',
    )
    session_id = request.GET.get('session') or ''
    date_seance = request.GET.get('date') or ''
    if session_id:
        qs = qs.filter(offre_module__session_id=session_id)
    if date_seance:
        qs = qs.filter(date_seance=date_seance)
    page_obj = Paginator(qs, 30).get_page(request.GET.get('page'))
    return render(request, 'formation_continue/presence_list.html', {
        'page_obj': page_obj,
        'presences': page_obj.object_list,
        'sessions': SessionFormation.objects.filter(active=True),
        'session_id': session_id,
        'date': date_seance,
    })


@login_required
@permission_required('formation_continue.add_presence', raise_exception=True)
def presence_create(request):
    """Saisie des présences : liste des séminaristes avec cases à cocher."""
    from datetime import date as date_cls

    offres = OffreModule.objects.select_related('session', 'module', 'formateur').order_by(
        '-session__annee', 'session__numero', 'module__code'
    )
    offre_id = (request.POST.get('offre_module') or request.GET.get('offre_module') or '').strip()
    date_seance_raw = (request.POST.get('date_seance') or request.GET.get('date_seance') or '').strip()
    offre = None
    date_seance = None
    lignes = []

    if offre_id:
        offre = get_object_or_404(offres, pk=offre_id)
    if date_seance_raw:
        try:
            date_seance = date_cls.fromisoformat(date_seance_raw)
        except ValueError:
            date_seance = None
            messages.error(request, 'Date de séance invalide.')

    if offre and date_seance:
        inscriptions = (
            Inscription.objects.filter(session=offre.session, modules=offre)
            .exclude(statut=Inscription.STATUT_ABANDON)
            .select_related('seminariste')
            .order_by('seminariste__nom', 'seminariste__prenom')
        )
        # Fallback : tous les inscrits de la session si aucun module n'est associé
        if not inscriptions.exists():
            inscriptions = (
                Inscription.objects.filter(session=offre.session)
                .exclude(statut=Inscription.STATUT_ABANDON)
                .select_related('seminariste')
                .order_by('seminariste__nom', 'seminariste__prenom')
            )

        existing = {
            p.inscription_id: p
            for p in Presence.objects.filter(offre_module=offre, date_seance=date_seance)
        }

        if request.method == 'POST' and 'enregistrer' in request.POST:
            presents = set(request.POST.getlist('present'))
            nb = 0
            for inscription in inscriptions:
                statut = (
                    Presence.STATUT_PRESENT
                    if str(inscription.pk) in presents
                    else Presence.STATUT_ABSENT
                )
                Presence.objects.update_or_create(
                    inscription=inscription,
                    offre_module=offre,
                    date_seance=date_seance,
                    defaults={'statut': statut},
                )
                nb += 1
            messages.success(
                request,
                f'Présences enregistrées pour {nb} séminariste(s) '
                f'({len(presents)} présent(s)).',
            )
            return redirect(
                f"{reverse('formation_continue:presence_create')}"
                f"?offre_module={offre.pk}&date_seance={date_seance.isoformat()}"
            )

        for inscription in inscriptions:
            presence = existing.get(inscription.pk)
            checked = False
            if presence:
                checked = presence.statut in {
                    Presence.STATUT_PRESENT,
                    Presence.STATUT_RETARD,
                }
            elif request.method == 'POST':
                checked = str(inscription.pk) in request.POST.getlist('present')
            lignes.append({
                'inscription': inscription,
                'seminariste': inscription.seminariste,
                'presence': presence,
                'checked': checked,
            })

    return render(request, 'formation_continue/presence_form.html', {
        'title': 'Saisie des présences',
        'offres': offres,
        'offre': offre,
        'offre_id': offre_id,
        'date_seance': date_seance.isoformat() if date_seance else (
            date_seance_raw or ('' if offre_id else date_cls.today().isoformat())
        ),
        'date_seance_obj': date_seance,
        'lignes': lignes,
        'ready': bool(offre and date_seance),
    })


@login_required
@permission_required('formation_continue.change_presence', raise_exception=True)
def presence_update(request, pk):
    obj = get_object_or_404(Presence, pk=pk)
    form = PresenceForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Présence mise à jour.')
        return redirect('formation_continue:presence_list')
    return render(request, 'formation_continue/presence_form.html', {
        'form': form,
        'title': 'Modifier la présence',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.delete_presence', raise_exception=True)
def presence_delete(request, pk):
    obj = get_object_or_404(Presence, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Présence supprimée.')
        return redirect('formation_continue:presence_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer la présence',
        'cancel_url': 'formation_continue:presence_list',
    })


# ---------- Brevets ----------

def _sessions_cloturees():
    return SessionFormation.objects.filter(cloturee=True).order_by('-annee', 'numero')


@login_required
@permission_required('formation_continue.view_brevet', raise_exception=True)
def brevet_list(request):
    qs = Brevet.objects.select_related('seminariste', 'session')
    session_id = request.GET.get('session') or ''
    q = (request.GET.get('q') or '').strip()
    if session_id:
        qs = qs.filter(session_id=session_id)
    if q:
        qs = qs.filter(
            Q(numero__icontains=q)
            | Q(seminariste__nom__icontains=q)
            | Q(seminariste__prenom__icontains=q)
        )
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    sessions_cloturees = _sessions_cloturees()
    return render(request, 'formation_continue/brevet_list.html', {
        'page_obj': page_obj,
        'brevets': page_obj.object_list,
        'sessions': sessions_cloturees,
        'session_id': session_id,
        'q': q,
        'has_session_cloturee': sessions_cloturees.exists(),
    })


@login_required
@permission_required('formation_continue.add_brevet', raise_exception=True)
def brevet_create(request):
    if not _sessions_cloturees().exists():
        messages.warning(
            request,
            'Les brevets ne sont disponibles qu’après clôture d’une session. '
            'Clôturez d’abord la session concernée.',
        )
        return redirect('formation_continue:cloture_session_list')

    form = BrevetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        if 'generer_pdf' in request.POST:
            messages.success(request, f'Brevet « {obj.numero} » enregistré. PDF généré.')
            return redirect('formation_continue:brevet_pdf', pk=obj.pk)
        messages.success(request, f'Brevet « {obj.numero} » enregistré. Vous pouvez générer le PDF.')
        return redirect('formation_continue:brevet_update', pk=obj.pk)
    return render(request, 'formation_continue/brevet_form.html', {
        'form': form,
        'title': 'Éditer un brevet',
    })


@login_required
@permission_required('formation_continue.change_brevet', raise_exception=True)
def brevet_update(request, pk):
    obj = get_object_or_404(Brevet.objects.select_related('session'), pk=pk)
    if not obj.session.cloturee:
        messages.error(
            request,
            'Ce brevet est lié à une session non clôturée et n’est plus modifiable '
            'tant que la session n’est pas clôturée.',
        )
        return redirect('formation_continue:brevet_list')

    form = BrevetForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if 'generer_pdf' in request.POST:
            messages.success(request, 'Brevet mis à jour. PDF généré.')
            return redirect('formation_continue:brevet_pdf', pk=obj.pk)
        messages.success(request, 'Brevet mis à jour.')
        return redirect('formation_continue:brevet_update', pk=obj.pk)
    return render(request, 'formation_continue/brevet_form.html', {
        'form': form,
        'title': f'Modifier — {obj.numero}',
        'object': obj,
    })


@login_required
@permission_required('formation_continue.view_brevet', raise_exception=True)
def brevet_pdf(request, pk):
    """Génère et affiche le PDF du brevet (réservé aux sessions clôturées)."""
    brevet = get_object_or_404(
        Brevet.objects.select_related('seminariste', 'session').prefetch_related('modules_valides'),
        pk=pk,
    )
    if not brevet.session.cloturee:
        messages.error(
            request,
            'Le PDF du brevet n’est disponible qu’après clôture de la session.',
        )
        return redirect('formation_continue:cloture_session_detail', pk=brevet.session_id)
    pdf_bytes, filename = generer_brevet_pdf(brevet, enregistrer=True)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@permission_required('formation_continue.delete_brevet', raise_exception=True)
def brevet_delete(request, pk):
    obj = get_object_or_404(Brevet.objects.select_related('session'), pk=pk)
    if not obj.session.cloturee:
        messages.error(request, 'Suppression impossible : session non clôturée.')
        return redirect('formation_continue:brevet_list')
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Brevet supprimé.')
        return redirect('formation_continue:brevet_list')
    return render(request, 'formation_continue/confirm_delete.html', {
        'object': obj,
        'title': 'Supprimer le brevet',
        'cancel_url': 'formation_continue:brevet_list',
    })
