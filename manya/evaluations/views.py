"""
Vues pour l'application evaluations
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, IntegerField, Value
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from urllib.parse import urlencode
from decimal import Decimal
from .models import TypeEvaluation, Session, Evaluation, Note
from students.models import Inscription, Student
from academics.models import AnneeAcademique, Classe, ElementConstitutif, Filiere
from academics.utils import NO_ACTIVE_ANNEE_ERROR
from .forms import (
    TypeEvaluationForm,
    SessionForm,
    EvaluationForm,
    NoteForm,
    NoteConsultationFilterForm,
    EvaluationListFilterForm,
    NoteImportExcelForm,
    enseignant_ec_info,
)
from .pdf import build_fiche_cotation_pdf
from .excel import (
    build_fiche_cotation_download_name,
    build_lignes_cotation,
    build_notes_import_template,
    parse_notes_import_workbook,
)
from .session_workflow import (
    assert_session_writable,
    inscriptions_rattrapage_pour_ec,
    ecs_rattrapage_pour_classe,
    verrouiller_session,
    deverrouiller_session,
    prepare_rattrapage_session,
    workflow_etat_session,
    SessionWorkflowError,
)
from academics.models import Promotion


def _inscriptions_annee_active():
    """Inscriptions actives de l'année académique en cours."""
    annee = AnneeAcademique.get_active()
    if not annee:
        return Inscription.objects.none(), annee
    qs = (
        Inscription.objects.filter(
            annee_academique=annee,
            statut='inscrit',
            classe__isnull=False,
        )
        .select_related('etudiant', 'classe', 'classe__promotion')
        .order_by('classe__promotion__code', 'etudiant__numero_etudiant')
    )
    return qs, annee


def _note_selection_from_request(request):
    """Extrait session, cours (EC), classe et évaluation depuis GET ou POST."""
    selected = {}
    for key in ('session', 'ec', 'classe', 'evaluation'):
        value = request.GET.get(key) or request.POST.get(key)
        if value and str(value).isdigit():
            selected[key] = int(value)
    return selected


def _fiche_cotation_avec_notes(request) -> bool:
    """True si la fiche doit inclure les notes déjà saisies."""
    raw = (request.GET.get('avec_notes') or request.POST.get('avec_notes') or '0').strip().lower()
    return raw in ('1', 'true', 'oui', 'yes')


def _redirect_note_list(selected):
    base = reverse('evaluations:note_list')
    if selected:
        return redirect(f'{base}?{urlencode(selected)}')
    return redirect(base)


def _note_valeur_saisie(note):
    """Valeur formatée pour un champ HTML type=\"number\"."""
    if note is None or note.absent or note.note is None:
        return ''
    text = format(note.note, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


def _charger_etudiants_notes(evaluation, inscriptions):
    """Liste des étudiants avec leurs notes existantes pour une évaluation."""
    inscriptions = list(inscriptions)
    etudiant_ids = [inscription.etudiant_id for inscription in inscriptions]
    notes_par_etudiant = {
        note.etudiant_id: note
        for note in Note.objects.filter(
            evaluation=evaluation,
            etudiant_id__in=etudiant_ids,
        )
    }
    etudiants_notes = []
    for inscription in inscriptions:
        etudiant = inscription.etudiant
        note = notes_par_etudiant.get(etudiant.id)
        etudiants_notes.append({
            'etudiant': etudiant,
            'note': note,
            'note_valeur': _note_valeur_saisie(note),
            'note_saisie': note is not None and (note.absent or note.note is not None),
        })
    return etudiants_notes


def _etudiant_tri_alphabetique_key(etudiant):
    return (
        (etudiant.nom or '').strip().upper(),
        (etudiant.prenom or '').strip().upper(),
        etudiant.numero_etudiant or '',
    )


def _inscriptions_classe(classe_obj, annee):
    return (
        Inscription.objects.filter(
            classe=classe_obj,
            annee_academique=annee,
        )
        .eligibles_listes()
        .select_related('etudiant')
        .order_by('etudiant__nom', 'etudiant__prenom', 'etudiant__numero_etudiant')
    )


def _etudiants_cotation_ordre_alphabetique(inscriptions):
    """Tri NOM, PRÉNOM pour la fiche de cotation (PDF / Excel)."""
    etudiants = [inscription.etudiant for inscription in inscriptions]
    return sorted(etudiants, key=_etudiant_tri_alphabetique_key)


def _filtrer_inscriptions_recherche(inscriptions, q):
    if not q:
        return inscriptions
    return inscriptions.filter(
        Q(etudiant__numero_etudiant__icontains=q)
        | Q(etudiant__nom__icontains=q)
        | Q(etudiant__prenom__icontains=q)
    )


def _evaluation_consultation(cleaned_data):
    """Évaluation cible pour la consultation (sélectionnée ou unique)."""
    evaluation = cleaned_data.get('evaluation')
    if evaluation:
        return evaluation
    session = cleaned_data.get('session')
    ec = cleaned_data.get('ec')
    if not session or not ec:
        return None
    evaluations = (
        Evaluation.objects.filter(ec=ec, session=session, active=True)
        .select_related('type_evaluation', 'ec', 'session')
        .order_by('type_evaluation__ordre', 'type_evaluation__nom')
    )
    if evaluations.count() == 1:
        return evaluations.first()
    return None


def _filtrer_lignes_presence(lignes, presence):
    if not presence:
        return lignes
    filtered = []
    for ligne in lignes:
        note = ligne.get('note')
        if presence == 'present':
            if note and not note.absent:
                filtered.append(ligne)
        elif presence == 'absent':
            if note and note.absent:
                filtered.append(ligne)
        elif presence == 'justifie':
            if note and note.absent and note.justifie:
                filtered.append(ligne)
        elif presence == 'non_justifie':
            if note and note.absent and not note.justifie:
                filtered.append(ligne)
    return filtered


def _lignes_consultation_classe(classe, annee, cleaned_data):
    """Liste complète des étudiants de la classe avec leurs notes (ou vide)."""
    inscriptions = _filtrer_inscriptions_recherche(
        _inscriptions_classe(classe, annee),
        cleaned_data.get('q'),
    )
    evaluation = _evaluation_consultation(cleaned_data)
    if evaluation:
        etudiants_data = _charger_etudiants_notes(evaluation, inscriptions)
    else:
        etudiants_data = [
            {
                'etudiant': inscription.etudiant,
                'note': None,
                'note_valeur': '',
                'note_saisie': False,
            }
            for inscription in inscriptions
        ]
    lignes = [
        {
            'etudiant': item['etudiant'],
            'note': item['note'],
            'evaluation': evaluation,
        }
        for item in etudiants_data
    ]
    return _filtrer_lignes_presence(lignes, cleaned_data.get('presence'))


def _evaluations_avec_compteur(ec_obj, session_id, etudiant_ids):
    return (
        Evaluation.objects.filter(
            ec=ec_obj,
            session_id=session_id,
            active=True,
        )
        .select_related('type_evaluation')
        .annotate(
            nb_notes_saisies=Count(
                'notes_etudiants',
                filter=Q(
                    notes_etudiants__etudiant_id__in=etudiant_ids,
                ) & (
                    Q(notes_etudiants__absent=True) | Q(notes_etudiants__note__isnull=False)
                ),
                distinct=True,
            ),
        )
        .order_by('-nb_notes_saisies', 'type_evaluation__ordre', 'type_evaluation__nom')
    )


def _evaluation_selectionnee(selected, evaluations):
    """Choisit l'évaluation : sélection utilisateur ou celle avec le plus de notes."""
    if not evaluations:
        return None
    if selected.get('evaluation'):
        return evaluations.filter(pk=selected['evaluation']).first()
    return evaluations.first()


def _ecs_pour_filiere_et_semestre(filiere, semestre):
    """EC actifs du semestre, limités à la filière de la classe."""
    qs = (
        ElementConstitutif.objects.filter(ue__semestre=semestre, active=True)
        .select_related('ue', 'ue__filiere', 'professeur')
    )
    if filiere:
        qs = qs.filter(ue__filiere=filiere)
    else:
        qs = qs.filter(ue__filiere__isnull=True)
    return qs.order_by('ue__ordre', 'ue__code', 'ordre', 'code')


def _ecs_pour_classe_et_session(classe_obj, session_obj, annee):
    """EC actifs du semestre, strictement limités à la filière de la promotion."""
    filiere = classe_obj.promotion.filiere if classe_obj.promotion else None
    return _ecs_pour_filiere_et_semestre(filiere, session_obj.semestre)


def _effacer_note_etudiant(user, etudiant, evaluation):
    """Supprime la note saisie (retour à l'état « non saisie »)."""
    assert_session_writable(evaluation.session)
    deleted, _ = Note.objects.filter(
        etudiant=etudiant,
        evaluation=evaluation,
    ).delete()
    return deleted > 0


def _enregistrer_note_etudiant(user, etudiant, evaluation, *, note_value=None, absent=False, justifie=False):
    """Enregistre ou met à jour la note d'un étudiant pour une évaluation."""
    assert_session_writable(evaluation.session)
    if not note_value and not absent:
        return False

    note_obj, _created = Note.objects.get_or_create(
        etudiant=etudiant,
        evaluation=evaluation,
        defaults={'saisie_par': user},
    )
    if absent:
        note_obj.absent = True
        note_obj.note = None
        note_obj.justifie = justifie
    else:
        note_obj.absent = False
        note_obj.note = note_value
        note_obj.justifie = False
        note_obj.note_sur = evaluation.note_max

    note_obj.modifie_par = user
    note_obj.save()
    return True


def _enregistrer_notes_etudiants(request, inscriptions, evaluation):
    """Enregistre les notes saisies pour une évaluation et une liste d'inscriptions."""
    enregistrees = 0
    effacees = 0
    for inscription in inscriptions:
        etudiant = inscription.etudiant
        note_value = (request.POST.get(f'note_{etudiant.id}') or '').strip()
        absent = request.POST.get(f'absent_{etudiant.id}') == 'on'
        justifie = request.POST.get(f'justifie_{etudiant.id}') == 'on'
        had_note = request.POST.get(f'had_note_{etudiant.id}') == '1'

        if not note_value and not absent:
            if had_note:
                if _effacer_note_etudiant(request.user, etudiant, evaluation):
                    effacees += 1
            continue

        if _enregistrer_note_etudiant(
            request.user,
            etudiant,
            evaluation,
            note_value=Decimal(note_value.replace(',', '.')) if note_value else None,
            absent=absent,
            justifie=justifie,
        ):
            enregistrees += 1
    return enregistrees, effacees


def _get_note_saisie_context(selected):
    """Charge le contexte complet de saisie (session, classe, EC, évaluation, étudiants)."""
    if not all(selected.get(key) for key in ('session', 'classe', 'ec', 'evaluation')):
        return None

    annee = AnneeAcademique.get_active()
    if not annee:
        return None

    session_obj = Session.objects.filter(pk=selected['session'], active=True).select_related('semestre').first()
    classe_obj = (
        Classe.objects.filter(pk=selected['classe'], active=True)
        .select_related('promotion', 'promotion__filiere', 'promotion__filiere__section')
        .first()
    )
    ec_obj = (
        ElementConstitutif.objects.filter(pk=selected['ec'], active=True)
        .select_related('ue', 'ue__filiere')
        .first()
    )
    evaluation_obj = (
        Evaluation.objects.filter(
            pk=selected['evaluation'],
            ec=ec_obj,
            session=session_obj,
            active=True,
        )
        .select_related('type_evaluation', 'ec', 'session')
        .first()
    )
    if not all((session_obj, classe_obj, ec_obj, evaluation_obj)):
        return None

    filiere = classe_obj.promotion.filiere if classe_obj.promotion else None
    if filiere and ec_obj.ue.filiere_id != filiere.id:
        return None
    if ec_obj.ue.semestre_id != session_obj.semestre_id:
        return None

    inscriptions = _inscriptions_classe(classe_obj, annee)
    if session_obj.numero == 2 and ec_obj:
        inscriptions = inscriptions_rattrapage_pour_ec(classe_obj, annee, session_obj, ec_obj)
    etudiants_notes = _charger_etudiants_notes(evaluation_obj, inscriptions)
    return {
        'annee': annee,
        'session': session_obj,
        'classe': classe_obj,
        'ec': ec_obj,
        'evaluation': evaluation_obj,
        'inscriptions': inscriptions,
        'etudiants_notes': etudiants_notes,
        'selected': selected,
    }


def _get_fiche_cotation_context(selected):
    """Contexte fiche de cotation vierge (liste des étudiants, sans notes)."""
    if not all(selected.get(key) for key in ('session', 'classe', 'ec')):
        return None

    annee = AnneeAcademique.get_active()
    if not annee:
        return None

    session_obj = Session.objects.filter(pk=selected['session'], active=True).select_related('semestre').first()
    classe_obj = (
        Classe.objects.filter(pk=selected['classe'], active=True)
        .select_related('promotion', 'promotion__filiere', 'promotion__filiere__section')
        .first()
    )
    ec_obj = (
        ElementConstitutif.objects.filter(pk=selected['ec'], active=True)
        .select_related('ue', 'ue__filiere', 'professeur')
        .first()
    )
    if not all((session_obj, classe_obj, ec_obj)):
        return None

    filiere = classe_obj.promotion.filiere if classe_obj.promotion else None
    if filiere and ec_obj.ue.filiere_id != filiere.id:
        return None
    if ec_obj.ue.semestre_id != session_obj.semestre_id:
        return None

    inscriptions = _inscriptions_classe(classe_obj, annee)
    if session_obj.numero == 2:
        inscriptions = inscriptions_rattrapage_pour_ec(classe_obj, annee, session_obj, ec_obj)

    return {
        'annee': annee,
        'session': session_obj,
        'classe': classe_obj,
        'ec': ec_obj,
        'etudiants': _etudiants_cotation_ordre_alphabetique(inscriptions),
        'selected': selected,
    }


# ========== TYPES D'EVALUATION ==========
@login_required
def type_evaluation_list(request):
    types = TypeEvaluation.objects.all().order_by('ordre', 'nom')
    return render(request, 'evaluations/type_evaluation_list.html', {'types': types})


@login_required
def type_evaluation_create(request):
    if request.method == 'POST':
        form = TypeEvaluationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Type d\'évaluation créé avec succès!')
            return redirect('evaluations:type_evaluation_list')
    else:
        form = TypeEvaluationForm()
    return render(request, 'evaluations/type_evaluation_form.html', {'form': form, 'title': 'Nouveau Type d\'Évaluation'})


@login_required
def type_evaluation_update(request, pk):
    type_eval = get_object_or_404(TypeEvaluation, pk=pk)
    if request.method == 'POST':
        form = TypeEvaluationForm(request.POST, instance=type_eval)
        if form.is_valid():
            form.save()
            messages.success(request, 'Type d\'évaluation modifié avec succès!')
            return redirect('evaluations:type_evaluation_list')
    else:
        form = TypeEvaluationForm(instance=type_eval)
    return render(request, 'evaluations/type_evaluation_form.html', {'form': form, 'title': 'Modifier Type d\'Évaluation', 'object': type_eval})


@login_required
def type_evaluation_delete(request, pk):
    type_eval = get_object_or_404(TypeEvaluation, pk=pk)
    if request.method == 'POST':
        type_eval.delete()
        messages.success(request, 'Type d\'évaluation supprimé avec succès!')
        return redirect('evaluations:type_evaluation_list')
    return render(request, 'evaluations/type_evaluation_confirm_delete.html', {'type_eval': type_eval})


# ========== SESSIONS ==========
@login_required
def session_list(request):
    annee = AnneeAcademique.get_active()
    sessions = (
        Session.pour_annee(annee)
        .select_related('semestre', 'annee_academique')
        .order_by('semestre__numero', 'numero')
    )
    paginator = Paginator(sessions, 10)
    page = request.GET.get('page')
    sessions_page = paginator.get_page(page)
    session_items = [
        {'session': s, 'workflow': workflow_etat_session(s)}
        for s in sessions_page.object_list
    ]
    return render(request, 'evaluations/session_list.html', {
        'sessions': sessions_page,
        'session_items': session_items,
        'annee': annee,
    })


@login_required
def session_create(request):
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Session créée avec succès!')
            return redirect('evaluations:session_list')
    else:
        form = SessionForm()
    return render(request, 'evaluations/session_form.html', {'form': form, 'title': 'Nouvelle Session'})


@login_required
def session_update(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, 'Session modifiée avec succès!')
            return redirect('evaluations:session_list')
    else:
        form = SessionForm(instance=session)
    return render(request, 'evaluations/session_form.html', {'form': form, 'title': 'Modifier Session', 'object': session})


@login_required
def session_delete(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        session.delete()
        messages.success(request, 'Session supprimée avec succès!')
        return redirect('evaluations:session_list')
    return render(request, 'evaluations/session_confirm_delete.html', {'session': session})


@login_required
def session_verrouiller(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        try:
            verrouiller_session(session)
            label = 'principale' if session.numero == 1 else 'de rattrapage'
            messages.success(request, f'Session {label} verrouillée.')
        except SessionWorkflowError as exc:
            messages.error(request, str(exc))
    return redirect('evaluations:session_list')


@login_required
def session_deverrouiller(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        try:
            deverrouiller_session(session)
            messages.success(request, 'Session déverrouillée.')
        except SessionWorkflowError as exc:
            messages.error(request, str(exc))
    return redirect('evaluations:session_list')


@login_required
def session_prepare_rattrapage(request, pk):
    session = get_object_or_404(Session, pk=pk, numero=1)
    promotions = Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre')

    if request.method == 'POST':
        promotion_id = request.POST.get('promotion')
        promotion = get_object_or_404(Promotion, pk=promotion_id, active=True)
        try:
            result = prepare_rattrapage_session(session, promotion)
            messages.success(
                request,
                f'Session de rattrapage prête ({result["ecs_ajournes"]} EC concerné(s), '
                f'{result["evaluations_crees"]} évaluation(s) créée(s)).',
            )
            return redirect('evaluations:session_list')
        except SessionWorkflowError as exc:
            messages.error(request, str(exc))

    return render(request, 'evaluations/session_prepare_rattrapage.html', {
        'session': session,
        'promotions': promotions,
        'workflow': workflow_etat_session(session),
    })


# ========== EVALUATIONS ==========
@login_required
def evaluation_list(request):
    annee = AnneeAcademique.get_active()
    filter_form = EvaluationListFilterForm(request.GET or None, annee=annee)
    evaluations_qs = (
        Evaluation.objects.select_related(
            'ec', 'session', 'session__semestre', 'type_evaluation', 'annee_academique',
        )
        .order_by('session__semestre__numero', 'session__numero', 'ec__code', 'type_evaluation__ordre')
    )
    if annee:
        evaluations_qs = evaluations_qs.filter(annee_academique=annee)
    else:
        evaluations_qs = evaluations_qs.none()
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)

    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        if q:
            evaluations_qs = evaluations_qs.filter(
                Q(code__icontains=q)
                | Q(nom__icontains=q)
                | Q(ec__code__icontains=q)
                | Q(ec__nom__icontains=q)
            )
        semestre = filter_form.cleaned_data.get('semestre')
        if semestre:
            evaluations_qs = evaluations_qs.filter(session__semestre=semestre)
        filiere = filter_form.cleaned_data.get('filiere')
        if filiere:
            evaluations_qs = evaluations_qs.filter(ec__ue__filiere=filiere)
        session = filter_form.cleaned_data.get('session')
        if session:
            evaluations_qs = evaluations_qs.filter(session=session)
        type_evaluation = filter_form.cleaned_data.get('type_evaluation')
        if type_evaluation:
            evaluations_qs = evaluations_qs.filter(type_evaluation=type_evaluation)
        ec = filter_form.cleaned_data.get('ec')
        if ec:
            evaluations_qs = evaluations_qs.filter(ec=ec)

    filter_query = request.GET.copy()
    filter_query.pop('page', None)
    has_filters = any(v for k, v in filter_query.items() if v)

    paginator = Paginator(evaluations_qs, 15)
    page = request.GET.get('page')
    evaluations = paginator.get_page(page)
    return render(request, 'evaluations/evaluation_list.html', {
        'evaluations': evaluations,
        'annee': annee,
        'filter_form': filter_form,
        'has_filters': has_filters,
        'filter_query': filter_query.urlencode(),
    })


@login_required
def evaluation_create(request):
    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Évaluation créée avec succès!')
            return redirect('evaluations:evaluation_list')
    else:
        form = EvaluationForm()
    return render(request, 'evaluations/evaluation_form.html', {'form': form, 'title': 'Nouvelle Évaluation'})


@login_required
def evaluation_update(request, pk):
    evaluation = get_object_or_404(
        Evaluation.objects.select_related('ec__ue__filiere', 'session'),
        pk=pk,
    )
    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=evaluation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Évaluation modifiée avec succès!')
            return redirect('evaluations:evaluation_list')
    else:
        form = EvaluationForm(instance=evaluation)
    return render(request, 'evaluations/evaluation_form.html', {'form': form, 'title': 'Modifier Évaluation', 'object': evaluation})


@login_required
def evaluation_delete(request, pk):
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if request.method == 'POST':
        evaluation.delete()
        messages.success(request, 'Évaluation supprimée avec succès!')
        return redirect('evaluations:evaluation_list')
    return render(request, 'evaluations/evaluation_confirm_delete.html', {'evaluation': evaluation})


@login_required
def api_ecs_evaluation(request):
    """EC actifs pour une filière et le semestre d'une session (formulaire évaluation)."""
    filiere_id = request.GET.get('filiere_id')
    session_id = request.GET.get('session_id')
    if not filiere_id or not session_id:
        return JsonResponse({'results': []})

    filiere = Filiere.objects.filter(pk=filiere_id, active=True).first()
    session = Session.objects.filter(pk=session_id, active=True).select_related('semestre').first()
    if not filiere or not session:
        return JsonResponse({'results': []})

    ecs = _ecs_pour_filiere_et_semestre(filiere, session.semestre)
    data = []
    for ec in ecs:
        professeur, responsable = enseignant_ec_info(ec)
        data.append({
            'id': ec.pk,
            'text': f'{ec.code} — {ec.nom}',
            'code': ec.code,
            'professeur': professeur,
            'responsable_id': responsable.pk if responsable else None,
        })
    return JsonResponse({'results': data})


# ========== NOTES ==========
@login_required
def note_list(request):
    """Saisie des notes : session → classe → cours (EC) → évaluation → tableau."""
    selected = _note_selection_from_request(request)
    annee = AnneeAcademique.get_active()

    sessions = (
        Session.pour_annee(annee)
        .filter(active=True)
        .select_related('semestre', 'annee_academique')
        .order_by('-semestre__numero', '-numero')
    )

    ecs = ElementConstitutif.objects.none()
    classes = Classe.objects.none()
    evaluations = Evaluation.objects.none()
    etudiants_notes = []
    session_obj = None
    ec_obj = None
    classe_obj = None
    evaluation_obj = None
    filiere_obj = None
    notes_hors_classe = False

    if selected.get('session'):
        session_obj = get_object_or_404(Session, pk=selected['session'])
        classes = (
            Classe.objects.filter(active=True)
            .select_related('promotion', 'promotion__filiere')
            .order_by('promotion__filiere__code', 'promotion__code', 'code')
        )

    if selected.get('session') and selected.get('classe'):
        classe_obj = get_object_or_404(
            Classe.objects.select_related('promotion', 'promotion__filiere'),
            pk=selected['classe'],
            active=True,
        )
        filiere_obj = classe_obj.promotion.filiere
        ecs = _ecs_pour_classe_et_session(classe_obj, session_obj, annee)
        if session_obj.numero == 2 and annee:
            ecs = ecs_rattrapage_pour_classe(classe_obj, session_obj, annee, ecs)
        if annee:
            etudiant_ids_ecs = list(
                _inscriptions_classe(classe_obj, annee).values_list('etudiant_id', flat=True)
            )
            if etudiant_ids_ecs:
                ecs = ecs.annotate(
                    nb_notes_saisies=Count(
                        'evaluations__notes_etudiants__etudiant',
                        filter=Q(
                            evaluations__session=session_obj,
                            evaluations__active=True,
                            evaluations__notes_etudiants__etudiant_id__in=etudiant_ids_ecs,
                        ) & (
                            Q(evaluations__notes_etudiants__absent=True)
                            | Q(evaluations__notes_etudiants__note__isnull=False)
                        ),
                        distinct=True,
                    ),
                )
            else:
                ecs = ecs.annotate(nb_notes_saisies=Value(0, output_field=IntegerField()))
        else:
            ecs = ecs.annotate(nb_notes_saisies=Value(0, output_field=IntegerField()))

        if selected.get('ec') and not ecs.filter(pk=selected['ec']).exists():
            selected = dict(selected)
            selected.pop('ec', None)
            selected.pop('evaluation', None)

    if selected.get('session') and selected.get('classe') and selected.get('ec'):
        ec_obj = get_object_or_404(
            ElementConstitutif.objects.select_related('ue', 'ue__filiere'),
            pk=selected['ec'],
        )
        etudiant_ids = []
        if annee and classe_obj:
            etudiant_ids = list(
                _inscriptions_classe(classe_obj, annee).values_list('etudiant_id', flat=True)
            )
        evaluations = _evaluations_avec_compteur(ec_obj, selected['session'], etudiant_ids)
        evaluation_obj = _evaluation_selectionnee(selected, evaluations)
        if evaluation_obj and not selected.get('evaluation'):
            selected = dict(selected)
            selected['evaluation'] = evaluation_obj.pk

    if evaluation_obj and classe_obj:
        if not annee:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            inscriptions = _inscriptions_classe(classe_obj, annee)
            if session_obj.numero == 2 and ec_obj:
                inscriptions = inscriptions_rattrapage_pour_ec(
                    classe_obj, annee, session_obj, ec_obj,
                )

            if request.method == 'POST' and 'enregistrer_notes' in request.POST:
                if session_obj.verrouillee:
                    messages.error(request, 'Session verrouillée : saisie impossible.')
                    return _redirect_note_list(selected)
                try:
                    enregistrees, effacees = _enregistrer_notes_etudiants(
                        request, inscriptions, evaluation_obj,
                    )
                except PermissionDenied as exc:
                    messages.error(request, str(exc))
                    return _redirect_note_list(selected)
                if enregistrees or effacees:
                    parts = []
                    if enregistrees:
                        parts.append(f'{enregistrees} note(s) enregistrée(s)')
                    if effacees:
                        parts.append(f'{effacees} note(s) effacée(s)')
                    messages.success(
                        request,
                        f"{' — '.join(parts)} — {evaluation_obj.type_evaluation.nom} ({classe_obj.code}).",
                    )
                else:
                    messages.info(request, 'Aucune modification enregistrée.')
                return _redirect_note_list(selected)

            etudiants_notes = _charger_etudiants_notes(evaluation_obj, inscriptions)
            if not any(item.get('note_saisie') for item in etudiants_notes):
                notes_hors_classe = Note.objects.filter(
                    evaluation__ec=ec_obj,
                    evaluation__session_id=selected['session'],
                ).exclude(etudiant_id__in=etudiant_ids).exists()

    notes_saisies_count = sum(1 for item in etudiants_notes if item.get('note_saisie'))
    notes_restantes_count = max(len(etudiants_notes) - notes_saisies_count, 0)

    return render(request, 'evaluations/note_list.html', {
        'sessions': sessions,
        'ecs': ecs,
        'classes': classes,
        'evaluations': evaluations,
        'etudiants_notes': etudiants_notes,
        'notes_saisies_count': notes_saisies_count,
        'notes_restantes_count': notes_restantes_count,
        'selected': selected,
        'session_obj': session_obj,
        'ec_obj': ec_obj,
        'classe_obj': classe_obj,
        'evaluation_obj': evaluation_obj,
        'filiere_obj': filiere_obj,
        'notes_hors_classe': notes_hors_classe,
        'annee': annee,
        'session_verrouillee': bool(session_obj and session_obj.verrouillee),
        'session_rattrapage': bool(session_obj and session_obj.numero == 2),
    })


@login_required
def fiche_cotation_pdf(request):
    """Fiche de cotation PDF (vierge ou avec notes saisies)."""
    selected = _note_selection_from_request(request)
    if not AnneeAcademique.get_active():
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        return redirect('evaluations:note_list')
    contexte = _get_fiche_cotation_context(selected)
    if not contexte:
        messages.error(request, 'Sélectionnez la session, la classe et le cours.')
        return redirect('evaluations:note_list')

    avec_notes = _fiche_cotation_avec_notes(request)
    lignes_cotation = None
    if avec_notes:
        lignes_cotation, _, _ = build_lignes_cotation(
            contexte['ec'],
            contexte['session'],
            contexte['etudiants'],
            avec_notes=True,
        )

    pdf_buffer = build_fiche_cotation_pdf(
        annee=contexte['annee'],
        session=contexte['session'],
        classe=contexte['classe'],
        ec=contexte['ec'],
        etudiants=contexte['etudiants'],
        lignes_cotation=lignes_cotation,
        avec_notes=avec_notes,
    )
    ec_obj = contexte['ec']
    filename = build_fiche_cotation_download_name(
        ec_obj, extension='pdf', avec_notes=avec_notes,
    )
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def note_export_excel(request):
    """Télécharge une fiche Excel (TJ/10, EXAM/10, MOY/20) alignée sur le PDF."""
    selected = _note_selection_from_request(request)
    if not AnneeAcademique.get_active():
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        return redirect('evaluations:note_list')
    contexte = _get_fiche_cotation_context(selected)
    if not contexte:
        messages.error(request, 'Sélectionnez la session, la classe et le cours.')
        return redirect('evaluations:note_list')

    if not contexte['etudiants']:
        messages.warning(request, 'Aucun étudiant inscrit dans cette classe pour générer le fichier.')
        return _redirect_note_list(selected)
    if contexte['session'].verrouillee:
        messages.error(request, 'Session verrouillée : export impossible.')
        return _redirect_note_list(selected)

    avec_notes = _fiche_cotation_avec_notes(request)

    try:
        buffer, _file_token, filename = build_notes_import_template(
            annee=contexte['annee'],
            session=contexte['session'],
            classe=contexte['classe'],
            ec=contexte['ec'],
            etudiants=contexte['etudiants'],
            avec_notes=avec_notes,
        )
    except ImportError:
        messages.error(request, "La bibliothèque openpyxl n'est pas installée sur le serveur.")
        return _redirect_note_list(selected)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def note_import_excel(request):
    """Importe les notes TJ/EXAM depuis une fiche Excel remplie."""
    if request.method != 'POST':
        return redirect('evaluations:note_list')

    selected = _note_selection_from_request(request)
    if not AnneeAcademique.get_active():
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        return redirect('evaluations:note_list')
    contexte = _get_fiche_cotation_context(selected)
    if not contexte:
        messages.error(request, 'Sélectionnez la session, la classe et le cours.')
        return redirect('evaluations:note_list')
    if contexte['session'].verrouillee:
        messages.error(request, 'Session verrouillée : import impossible.')
        return _redirect_note_list(selected)

    form = NoteImportExcelForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Veuillez sélectionner un fichier Excel (.xlsx).')
        return _redirect_note_list(selected)

    etudiants_par_numero = {
        etudiant.numero_etudiant: etudiant
        for etudiant in contexte['etudiants']
    }

    try:
        uploaded = form.cleaned_data['fichier_excel']
        lignes, errors = parse_notes_import_workbook(
            uploaded,
            session=contexte['session'],
            classe=contexte['classe'],
            ec=contexte['ec'],
            etudiants_par_numero=etudiants_par_numero,
            filename=getattr(uploaded, 'name', None),
        )
    except ImportError:
        messages.error(request, "La bibliothèque openpyxl n'est pas installée sur le serveur.")
        return _redirect_note_list(selected)
    except ValueError as exc:
        messages.error(request, str(exc))
        return _redirect_note_list(selected)
    except Exception as exc:
        messages.error(request, f"Impossible de lire le fichier Excel : {exc}")
        return _redirect_note_list(selected)

    if errors:
        preview = '; '.join(errors[:5])
        suffix = f" … ({len(errors) - 5} autre(s))" if len(errors) > 5 else ''
        messages.warning(request, f"Import partiel — erreurs : {preview}{suffix}")

    imported = 0
    effacees = 0
    for ligne in lignes:
        try:
            if ligne.get('tj_evaluation'):
                if ligne.get('tj_value') is not None:
                    if _enregistrer_note_etudiant(
                        request.user,
                        ligne['etudiant'],
                        ligne['tj_evaluation'],
                        note_value=ligne['tj_value'],
                        absent=False,
                        justifie=False,
                    ):
                        imported += 1
                elif ligne.get('tj_effacer'):
                    if _effacer_note_etudiant(
                        request.user,
                        ligne['etudiant'],
                        ligne['tj_evaluation'],
                    ):
                        effacees += 1
            if ligne.get('exam_evaluation'):
                if ligne.get('exam_value') is not None:
                    if _enregistrer_note_etudiant(
                        request.user,
                        ligne['etudiant'],
                        ligne['exam_evaluation'],
                        note_value=ligne['exam_value'],
                        absent=False,
                        justifie=False,
                    ):
                        imported += 1
                elif ligne.get('exam_effacer'):
                    if _effacer_note_etudiant(
                        request.user,
                        ligne['etudiant'],
                        ligne['exam_evaluation'],
                    ):
                        effacees += 1
        except PermissionDenied as exc:
            messages.error(request, str(exc))
            return _redirect_note_list(selected)

    if imported or effacees:
        parts = []
        if imported:
            parts.append(f"{imported} cote{'s' if imported > 1 else ''} importée{'s' if imported > 1 else ''}")
        if effacees:
            parts.append(f"{effacees} cote{'s' if effacees > 1 else ''} effacée{'s' if effacees > 1 else ''}")
        messages.success(request, f"{' — '.join(parts)} depuis Excel.")
    elif not errors:
        messages.info(request, 'Aucune note à importer (colonnes TJ/10 et EXAM/10 vides).')

    return _redirect_note_list(selected)


@login_required
def note_consultation(request):
    """Consultation des notes : liste des étudiants (avec ou sans note saisie)."""
    filter_data = request.GET.copy()
    for key in ('session', 'filiere', 'classe', 'ec', 'evaluation'):
        if not filter_data.get(key):
            filter_data.pop(key, None)
    filter_form = NoteConsultationFilterForm(filter_data or None)
    annee = AnneeAcademique.get_active()
    lignes = []
    roster_mode = False
    evaluation_ctx = None

    if filter_form.is_valid():
        classe = filter_form.cleaned_data.get('classe')
        if classe and annee:
            roster_mode = True
            lignes = _lignes_consultation_classe(classe, annee, filter_form.cleaned_data)
            evaluation_ctx = _evaluation_consultation(filter_form.cleaned_data)
            lignes.sort(key=lambda ligne: _etudiant_tri_alphabetique_key(ligne['etudiant']))
        else:
            notes = (
                Note.objects.select_related(
                    'etudiant',
                    'evaluation',
                    'evaluation__ec',
                    'evaluation__ec__ue__filiere',
                    'evaluation__session',
                    'evaluation__type_evaluation',
                )
                .all()
            )
            q = filter_form.cleaned_data.get('q')
            if q:
                notes = notes.filter(
                    Q(etudiant__numero_etudiant__icontains=q)
                    | Q(etudiant__nom__icontains=q)
                    | Q(etudiant__prenom__icontains=q)
                )
            session = filter_form.cleaned_data.get('session')
            if session:
                notes = notes.filter(evaluation__session=session)
            filiere = filter_form.cleaned_data.get('filiere')
            if filiere:
                notes = notes.filter(evaluation__ec__ue__filiere=filiere)
            ec = filter_form.cleaned_data.get('ec')
            if ec:
                notes = notes.filter(evaluation__ec=ec)
            evaluation = filter_form.cleaned_data.get('evaluation')
            if evaluation:
                notes = notes.filter(evaluation=evaluation)
                evaluation_ctx = evaluation
            presence = filter_form.cleaned_data.get('presence')
            if presence == 'present':
                notes = notes.filter(absent=False)
            elif presence == 'absent':
                notes = notes.filter(absent=True)
            elif presence == 'justifie':
                notes = notes.filter(absent=True, justifie=True)
            elif presence == 'non_justifie':
                notes = notes.filter(absent=True, justifie=False)
            notes = notes.order_by('-date_saisie', 'etudiant__numero_etudiant')
            lignes = [
                {'etudiant': note.etudiant, 'note': note, 'evaluation': note.evaluation}
                for note in notes
            ]

    paginator = Paginator(lignes, 20)
    page = request.GET.get('page')
    lignes_page = paginator.get_page(page)

    filter_query = request.GET.copy()
    filter_query.pop('page', None)
    has_filters = any(v for k, v in filter_query.items() if v)
    notes_saisies_count = sum(1 for ligne in lignes if ligne.get('note') and (
        ligne['note'].absent or ligne['note'].note is not None
    ))

    return render(request, 'evaluations/note_consultation.html', {
        'lignes': lignes_page,
        'filter_form': filter_form,
        'has_filters': has_filters,
        'filter_query': filter_query.urlencode(),
        'roster_mode': roster_mode,
        'evaluation_ctx': evaluation_ctx,
        'notes_saisies_count': notes_saisies_count,
    })


@login_required
def note_create(request):
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.saisie_par = request.user
            note.save()
            messages.success(request, 'Note saisie avec succès!')
            return redirect('evaluations:note_consultation')
    else:
        form = NoteForm()
    return render(request, 'evaluations/note_form.html', {'form': form, 'title': 'Nouvelle Note'})


@login_required
def note_update(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if request.method == 'POST':
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            note_obj = form.save(commit=False)
            note_obj.modifie_par = request.user
            note_obj.save()
            messages.success(request, 'Note modifiée avec succès!')
            return redirect('evaluations:note_consultation')
    else:
        form = NoteForm(instance=note)
    return render(request, 'evaluations/note_form.html', {'form': form, 'title': 'Modifier Note', 'object': note})


@login_required
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note supprimée avec succès!')
        return redirect('evaluations:note_consultation')
    return render(request, 'evaluations/note_confirm_delete.html', {'note': note})


# ========== SAISIE MASSE DES NOTES ==========
@login_required
def saisie_masse_notes(request, evaluation_id):
    """Saisie de notes pour tous les étudiants d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    inscriptions, annee = _inscriptions_annee_active()
    if not annee:
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
    
    if request.method == 'POST':
        # Traiter la saisie en masse
        for inscription in inscriptions:
            etudiant = inscription.etudiant
            note_value = request.POST.get(f'note_{etudiant.id}')
            note_sur_value = request.POST.get(f'note_sur_{etudiant.id}')
            absent = request.POST.get(f'absent_{etudiant.id}') == 'on'
            justifie = request.POST.get(f'justifie_{etudiant.id}') == 'on'
            
            if note_value or absent:
                note, created = Note.objects.get_or_create(
                    etudiant=etudiant,
                    evaluation=evaluation,
                    defaults={'saisie_par': request.user}
                )
                if absent:
                    note.absent = True
                    note.note = None
                    note.justifie = justifie
                else:
                    note.absent = False
                    note.note = Decimal(note_value) if note_value else None
                    note.justifie = False
                
                if note_sur_value:
                    note.note_sur = Decimal(note_sur_value)
                
                note.save()
        
        messages.success(request, 'Notes saisies avec succès!')
        return redirect('evaluations:evaluation_list')
    
    # Préparer les données pour l'affichage
    etudiants_notes = _charger_etudiants_notes(evaluation, inscriptions)
    
    return render(request, 'evaluations/saisie_masse_notes.html', {
        'evaluation': evaluation,
        'etudiants_notes': etudiants_notes
    })


# ========== NOTE PAR ÉTUDIANT ==========
@login_required
def note_par_etudiant(request):
    """Saisie de notes par étudiant : affiche toutes les évaluations d'un étudiant pour une session"""
    etudiant = None
    session = None
    evaluations_notes = []

    if request.method == 'POST':
        etudiant_id = request.POST.get('etudiant')
        session_id = request.POST.get('session')

        if etudiant_id and session_id:
            etudiant = get_object_or_404(Student, pk=etudiant_id)
            session = get_object_or_404(Session, pk=session_id)

            # Récupérer les ECs du semestre de la session
            ecs = ElementConstitutif.objects.filter(
                ue__semestre=session.semestre,
                active=True
            ).select_related('ue').order_by('ue__ordre', 'ordre', 'code')

            # Récupérer les évaluations
            evaluations = Evaluation.objects.filter(
                ec__in=ecs,
                session=session,
                active=True
            ).select_related('ec', 'type_evaluation').order_by('ec', 'type_evaluation')

            for evaluation in evaluations:
                note = Note.objects.filter(etudiant=etudiant, evaluation=evaluation).first()
                evaluations_notes.append({
                    'evaluation': evaluation,
                    'note': note,
                })

            # Si c'est une soumission de notes (bouton "Enregistrer")
            if 'enregistrer_notes' in request.POST:
                for evaluation in evaluations:
                    note_value = request.POST.get(f'note_{evaluation.id}')
                    note_sur_value = request.POST.get(f'note_sur_{evaluation.id}')
                    absent = request.POST.get(f'absent_{evaluation.id}') == 'on'
                    justifie = request.POST.get(f'justifie_{evaluation.id}') == 'on'

                    if note_value or absent:
                        note_obj, created = Note.objects.get_or_create(
                            etudiant=etudiant,
                            evaluation=evaluation,
                            defaults={'saisie_par': request.user}
                        )
                        if absent:
                            note_obj.absent = True
                            note_obj.note = None
                            note_obj.justifie = justifie
                        else:
                            note_obj.absent = False
                            note_obj.note = Decimal(note_value) if note_value else None
                            note_obj.justifie = False

                        if note_sur_value:
                            note_obj.note_sur = Decimal(note_sur_value)

                        note_obj.modifie_par = request.user
                        note_obj.save()

                messages.success(request, f'Notes enregistrées pour {etudiant.nom_complet}')
                return redirect('evaluations:note_par_etudiant')

    etudiants = Student.objects.filter(statut='actif').order_by('numero_etudiant')
    annee = AnneeAcademique.get_active()
    sessions = (
        Session.pour_annee(annee)
        .filter(active=True)
        .select_related('semestre', 'annee_academique')
        .order_by('-semestre__numero', '-numero')
    )

    return render(request, 'evaluations/note_par_etudiant.html', {
        'etudiant': etudiant,
        'session': session,
        'evaluations_notes': evaluations_notes,
        'etudiants': etudiants,
        'sessions': sessions,
    })


# ========== NOTE PAR EC ==========
@login_required
def note_par_ec(request):
    """Saisie de notes par EC : affiche tous les étudiants d'un EC pour une session"""
    ec_selected = None
    session = None
    etudiants_notes = []

    if request.method == 'POST':
        ec_id = request.POST.get('ec')
        session_id = request.POST.get('session')

        if ec_id and session_id:
            ec_selected = get_object_or_404(ElementConstitutif, pk=ec_id)
            session = get_object_or_404(Session, pk=session_id)

            # Inscriptions de l'année académique active
            inscriptions, _annee = _inscriptions_annee_active()

            # Récupérer les évaluations pour cet EC dans cette session
            evaluations = Evaluation.objects.filter(
                ec=ec_selected,
                session=session,
                active=True
            ).select_related('type_evaluation').order_by('type_evaluation')

            for inscription in inscriptions:
                etudiant = inscription.etudiant
                notes_eval = []
                for evaluation in evaluations:
                    note = Note.objects.filter(etudiant=etudiant, evaluation=evaluation).first()
                    notes_eval.append({
                        'evaluation': evaluation,
                        'note': note,
                    })
                etudiants_notes.append({
                    'etudiant': etudiant,
                    'classe': inscription.classe,
                    'notes_eval': notes_eval,
                })

            # Si c'est une soumission de notes (bouton "Enregistrer")
            if 'enregistrer_notes' in request.POST:
                for inscription in inscriptions:
                    etudiant = inscription.etudiant
                    for evaluation in evaluations:
                        note_value = request.POST.get(f'note_{etudiant.id}_{evaluation.id}')
                        note_sur_value = request.POST.get(f'note_sur_{etudiant.id}_{evaluation.id}')
                        absent = request.POST.get(f'absent_{etudiant.id}_{evaluation.id}') == 'on'
                        justifie = request.POST.get(f'justifie_{etudiant.id}_{evaluation.id}') == 'on'

                        if note_value or absent:
                            note_obj, created = Note.objects.get_or_create(
                                etudiant=etudiant,
                                evaluation=evaluation,
                                defaults={'saisie_par': request.user}
                            )
                            if absent:
                                note_obj.absent = True
                                note_obj.note = None
                                note_obj.justifie = justifie
                            else:
                                note_obj.absent = False
                                note_obj.note = Decimal(note_value) if note_value else None
                                note_obj.justifie = False

                            if note_sur_value:
                                note_obj.note_sur = Decimal(note_sur_value)

                            note_obj.modifie_par = request.user
                            note_obj.save()

                messages.success(request, f'Notes enregistrées pour {ec_selected.code}')
                return redirect('evaluations:note_par_ec')

    ecs = ElementConstitutif.objects.filter(active=True).select_related('ue').order_by('ue__semestre', 'ue', 'ordre')
    annee = AnneeAcademique.get_active()
    sessions = (
        Session.pour_annee(annee)
        .filter(active=True)
        .select_related('semestre', 'annee_academique')
        .order_by('-semestre__numero', '-numero')
    )

    return render(request, 'evaluations/note_par_ec.html', {
        'ec_selected': ec_selected,
        'session': session,
        'etudiants_notes': etudiants_notes,
        'ecs': ecs,
        'sessions': sessions,
    })
