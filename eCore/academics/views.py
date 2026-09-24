"""
Vues pour l'application academics
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Prefetch, ProtectedError

from config.models import Etablissement
from .models import (
    Section, Faculte, Departement, Filiere, Promotion, Classe, Local,
    AnneeAcademique, Semestre,
    UniteEnseignement, ElementConstitutif
)
from .forms import (
    SectionForm, FaculteForm, DepartementForm, FiliereForm, PromotionForm, ClasseForm, LocalForm,
    AnneeAcademiqueForm, SemestreForm,
    UniteEnseignementForm, ElementConstitutifForm, UEListFilterForm
)
from students.models import Inscription


# ========== SECTIONS ==========
@login_required
def section_list(request):
    sections = Section.objects.select_related('etablissement').all().order_by('etablissement__code', 'code')
    paginator = Paginator(sections, 10)
    page = request.GET.get('page')
    sections = paginator.get_page(page)
    return render(request, 'academics/section_list.html', {'sections': sections})


@login_required
def section_create(request):
    if request.method == 'POST':
        form = SectionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Section créée avec succès!')
            return redirect('academics:section_list')
    else:
        form = SectionForm()
    return render(request, 'academics/section_form.html', {'form': form, 'title': 'Nouvelle Section'})


@login_required
def section_update(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if request.method == 'POST':
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            messages.success(request, 'Section modifiée avec succès!')
            return redirect('academics:section_list')
    else:
        form = SectionForm(instance=section)
    return render(request, 'academics/section_form.html', {'form': form, 'title': 'Modifier Section', 'object': section})


@login_required
def section_delete(request, pk):
    section = get_object_or_404(Section, pk=pk)
    if request.method == 'POST':
        section.delete()
        messages.success(request, 'Section supprimée avec succès!')
        return redirect('academics:section_list')
    return render(request, 'academics/section_confirm_delete.html', {'section': section})


# ========== FACULTES ==========
@login_required
def faculte_list(request):
    facultes = Faculte.objects.select_related('etablissement').all()
    paginator = Paginator(facultes, 15)
    facultes = paginator.get_page(request.GET.get('page'))
    return render(request, 'academics/faculte_list.html', {'facultes': facultes})


@login_required
def faculte_create(request):
    if request.method == 'POST':
        form = FaculteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculté créée avec succès.')
            return redirect('academics:faculte_list')
    else:
        form = FaculteForm(initial={'etablissement': Etablissement.get_pilote()})
    return render(request, 'academics/faculte_form.html', {'form': form, 'title': 'Nouvelle faculté'})


@login_required
def faculte_update(request, pk):
    faculte = get_object_or_404(Faculte, pk=pk)
    if request.method == 'POST':
        form = FaculteForm(request.POST, instance=faculte)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculté modifiée avec succès.')
            return redirect('academics:faculte_list')
    else:
        form = FaculteForm(instance=faculte)
    return render(request, 'academics/faculte_form.html', {
        'form': form,
        'title': 'Modifier la faculté',
        'object': faculte,
    })


@login_required
def faculte_delete(request, pk):
    faculte = get_object_or_404(Faculte, pk=pk)
    if request.method == 'POST':
        try:
            faculte.delete()
        except ProtectedError:
            messages.error(
                request,
                'Cette faculté a des départements ou des filières. Retirez-les avant de la supprimer.',
            )
            return redirect('academics:faculte_list')
        messages.success(request, 'Faculté supprimée avec succès.')
        return redirect('academics:faculte_list')
    return render(request, 'academics/faculte_confirm_delete.html', {'faculte': faculte})


# ========== DEPARTEMENTS ==========
@login_required
def departement_list(request):
    departements = Departement.objects.select_related('faculte', 'faculte__etablissement')
    faculte_id = request.GET.get('faculte')
    if faculte_id:
        departements = departements.filter(faculte_id=faculte_id)
    paginator = Paginator(departements, 15)
    departements = paginator.get_page(request.GET.get('page'))
    return render(request, 'academics/departement_list.html', {
        'departements': departements,
        'facultes': Faculte.objects.select_related('etablissement').all(),
        'faculte_id': faculte_id or '',
    })


@login_required
def departement_create(request):
    droit = Faculte.objects.filter(etablissement__code='UNIKIN', code='DROIT').first()
    if request.method == 'POST':
        form = DepartementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Département créé avec succès.')
            return redirect('academics:departement_list')
    else:
        form = DepartementForm(initial={'faculte': droit})
    return render(request, 'academics/departement_form.html', {
        'form': form,
        'title': 'Nouveau département',
    })


@login_required
def departement_update(request, pk):
    departement = get_object_or_404(Departement, pk=pk)
    if request.method == 'POST':
        form = DepartementForm(request.POST, instance=departement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Département modifié avec succès.')
            return redirect('academics:departement_list')
    else:
        form = DepartementForm(instance=departement)
    return render(request, 'academics/departement_form.html', {
        'form': form,
        'title': 'Modifier le département',
        'object': departement,
    })


@login_required
def departement_delete(request, pk):
    departement = get_object_or_404(Departement, pk=pk)
    if request.method == 'POST':
        departement.delete()
        messages.success(request, 'Département supprimé avec succès.')
        return redirect('academics:departement_list')
    return render(request, 'academics/departement_confirm_delete.html', {'departement': departement})


# ========== FILIERES ==========
@login_required
def filiere_list(request):
    filieres = Filiere.objects.select_related('section', 'faculte', 'departement')
    faculte_id = request.GET.get('faculte')
    if faculte_id:
        filieres = filieres.filter(faculte_id=faculte_id)
    paginator = Paginator(filieres, 20)
    filieres = paginator.get_page(request.GET.get('page'))
    return render(request, 'academics/filiere_list.html', {
        'filieres': filieres,
        'facultes': Faculte.objects.filter(etablissement__code='UNIKIN'),
        'faculte_id': faculte_id or '',
        'filter_query': f'faculte={faculte_id}' if faculte_id else '',
    })


@login_required
def filiere_create(request):
    if request.method == 'POST':
        form = FiliereForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Filière créée avec succès!')
            return redirect('academics:filiere_list')
    else:
        form = FiliereForm()
    return render(request, 'academics/filiere_form.html', {'form': form, 'title': 'Nouvelle Filière'})


@login_required
def filiere_update(request, pk):
    filiere = get_object_or_404(Filiere, pk=pk)
    if request.method == 'POST':
        form = FiliereForm(request.POST, instance=filiere)
        if form.is_valid():
            form.save()
            messages.success(request, 'Filière modifiée avec succès!')
            return redirect('academics:filiere_list')
    else:
        form = FiliereForm(instance=filiere)
    return render(request, 'academics/filiere_form.html', {'form': form, 'title': 'Modifier Filière', 'object': filiere})


@login_required
def filiere_delete(request, pk):
    filiere = get_object_or_404(Filiere, pk=pk)
    if request.method == 'POST':
        filiere.delete()
        messages.success(request, 'Filière supprimée avec succès!')
        return redirect('academics:filiere_list')
    return render(request, 'academics/filiere_confirm_delete.html', {'filiere': filiere})


# ========== ANNEE ACADEMIQUE ==========
@login_required
def annee_academique_list(request):
    annees = AnneeAcademique.objects.all().order_by('-annee_debut')
    paginator = Paginator(annees, 10)
    page = request.GET.get('page')
    annees = paginator.get_page(page)
    return render(request, 'academics/annee_academique_list.html', {'annees': annees})


@login_required
def annee_academique_create(request):
    if request.method == 'POST':
        form = AnneeAcademiqueForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Année académique créée avec succès!')
            return redirect('academics:annee_academique_list')
    else:
        form = AnneeAcademiqueForm()
    return render(request, 'academics/annee_academique_form.html', {'form': form, 'title': 'Nouvelle Année Académique'})


@login_required
def annee_academique_update(request, pk):
    annee = get_object_or_404(AnneeAcademique, pk=pk)
    if request.method == 'POST':
        form = AnneeAcademiqueForm(request.POST, instance=annee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Année académique modifiée avec succès!')
            return redirect('academics:annee_academique_list')
    else:
        form = AnneeAcademiqueForm(instance=annee)
    return render(request, 'academics/annee_academique_form.html', {'form': form, 'title': 'Modifier Année Académique', 'object': annee})


@login_required
def annee_academique_delete(request, pk):
    annee = get_object_or_404(AnneeAcademique, pk=pk)
    if request.method == 'POST':
        annee.delete()
        messages.success(request, 'Année académique supprimée avec succès!')
        return redirect('academics:annee_academique_list')
    return render(request, 'academics/annee_academique_confirm_delete.html', {'annee': annee})


# ========== PROMOTIONS ==========
@login_required
def promotion_list(request):
    promotions = Promotion.objects.select_related(
        'filiere', 'filiere__section', 'filiere__faculte', 'filiere__departement',
    ).order_by('filiere__faculte__code', 'filiere__code', 'ordre', 'code')
    faculte_id = request.GET.get('faculte')
    if faculte_id:
        promotions = promotions.filter(filiere__faculte_id=faculte_id)
    paginator = Paginator(promotions, 20)
    promotions = paginator.get_page(request.GET.get('page'))
    return render(request, 'academics/promotion_list.html', {
        'promotions': promotions,
        'facultes': Faculte.objects.filter(etablissement__code='UNIKIN'),
        'faculte_id': faculte_id or '',
        'filter_query': f'faculte={faculte_id}' if faculte_id else '',
    })


@login_required
def promotion_detail(request, pk):
    """Fiche détaillée d'une promotion : classes et étudiants inscrits."""
    promotion = get_object_or_404(
        Promotion.objects.select_related(
            'filiere', 'filiere__section', 'filiere__faculte', 'filiere__departement',
        ),
        pk=pk,
    )
    annee_active = AnneeAcademique.get_active()

    classes = (
        Classe.objects.filter(promotion=promotion)
        .select_related('local')
        .order_by('code')
    )

    inscriptions_annee = Inscription.objects.none()
    if annee_active:
        inscriptions_annee = (
            Inscription.objects.filter(
                classe__promotion=promotion,
                annee_academique=annee_active,
            )
            .eligibles_listes()
            .select_related('etudiant', 'classe')
            .order_by('classe__code', 'etudiant__numero_etudiant')
        )

    effectifs_par_classe = {}
    if annee_active:
        for ins in inscriptions_annee:
            if ins.classe_id:
                effectifs_par_classe[ins.classe_id] = effectifs_par_classe.get(ins.classe_id, 0) + 1

    classes_data = [
        {
            'classe': classe,
            'effectif': effectifs_par_classe.get(classe.pk, 0),
        }
        for classe in classes
    ]

    return render(request, 'academics/promotion_detail.html', {
        'promotion': promotion,
        'annee_active': annee_active,
        'classes_data': classes_data,
        'inscriptions': inscriptions_annee,
        'total_inscriptions': inscriptions_annee.count(),
    })


@login_required
def promotion_create(request):
    if request.method == 'POST':
        form = PromotionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Promotion créée avec succès!')
            return redirect('academics:promotion_list')
    else:
        form = PromotionForm()
    return render(request, 'academics/promotion_form.html', {'form': form, 'title': 'Nouvelle Promotion'})


@login_required
def promotion_update(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)
    if request.method == 'POST':
        form = PromotionForm(request.POST, instance=promotion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Promotion modifiée avec succès!')
            return redirect('academics:promotion_list')
    else:
        form = PromotionForm(instance=promotion)
    return render(request, 'academics/promotion_form.html', {'form': form, 'title': 'Modifier Promotion', 'object': promotion})


@login_required
def promotion_delete(request, pk):
    promotion = get_object_or_404(Promotion, pk=pk)
    if request.method == 'POST':
        promotion.delete()
        messages.success(request, 'Promotion supprimée avec succès!')
        return redirect('academics:promotion_list')
    return render(request, 'academics/promotion_confirm_delete.html', {'promotion': promotion})


# ========== LOCAUX ==========
@login_required
def local_list(request):
    locaux = Local.objects.all().order_by('code')
    paginator = Paginator(locaux, 10)
    page = request.GET.get('page')
    locaux = paginator.get_page(page)
    return render(request, 'academics/local_list.html', {'locaux': locaux})


@login_required
def local_create(request):
    if request.method == 'POST':
        form = LocalForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Local créé avec succès!')
            return redirect('academics:local_list')
    else:
        form = LocalForm()
    return render(request, 'academics/local_form.html', {
        'form': form,
        'title': 'Nouveau Local',
        'subtitle': 'Créer une salle ou un amphithéâtre',
    })


@login_required
def local_update(request, pk):
    local = get_object_or_404(Local, pk=pk)
    if request.method == 'POST':
        form = LocalForm(request.POST, instance=local)
        if form.is_valid():
            form.save()
            messages.success(request, 'Local modifié avec succès!')
            return redirect('academics:local_list')
    else:
        form = LocalForm(instance=local)
    return render(request, 'academics/local_form.html', {
        'form': form,
        'title': 'Modifier Local',
        'subtitle': f'Modifier {local.code}',
        'object': local,
    })


@login_required
def local_delete(request, pk):
    local = get_object_or_404(Local, pk=pk)
    if request.method == 'POST':
        local.delete()
        messages.success(request, 'Local supprimé avec succès!')
        return redirect('academics:local_list')
    return render(request, 'academics/local_confirm_delete.html', {'local': local})


# ========== CLASSES ==========
@login_required
def classe_list(request):
    classes = Classe.objects.select_related(
        'promotion', 'promotion__filiere', 'promotion__filiere__section',
        'promotion__filiere__faculte', 'local',
    ).order_by(
        'promotion__filiere__faculte__code',
        'promotion__filiere__code',
        'promotion__ordre',
        'code',
    )
    faculte_id = request.GET.get('faculte')
    if faculte_id:
        classes = classes.filter(promotion__filiere__faculte_id=faculte_id)
    paginator = Paginator(classes, 20)
    classes = paginator.get_page(request.GET.get('page'))
    return render(request, 'academics/classe_list.html', {
        'classes': classes,
        'facultes': Faculte.objects.filter(etablissement__code='UNIKIN'),
        'faculte_id': faculte_id or '',
        'filter_query': f'faculte={faculte_id}' if faculte_id else '',
    })


@login_required
def classe_create(request):
    if request.method == 'POST':
        form = ClasseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Classe créée avec succès!')
            return redirect('academics:classe_list')
    else:
        initial = {}
        promotion_id = request.GET.get('promotion')
        if promotion_id:
            initial['promotion'] = promotion_id
        form = ClasseForm(initial=initial)
    return render(request, 'academics/classe_form.html', {'form': form, 'title': 'Nouvelle Classe'})


@login_required
def classe_update(request, pk):
    classe = get_object_or_404(Classe, pk=pk)
    if request.method == 'POST':
        form = ClasseForm(request.POST, instance=classe)
        if form.is_valid():
            form.save()
            messages.success(request, 'Classe modifiée avec succès!')
            return redirect('academics:classe_list')
    else:
        form = ClasseForm(instance=classe)
    return render(request, 'academics/classe_form.html', {'form': form, 'title': 'Modifier Classe', 'object': classe})


@login_required
def classe_delete(request, pk):
    classe = get_object_or_404(Classe, pk=pk)
    if request.method == 'POST':
        classe.delete()
        messages.success(request, 'Classe supprimée avec succès!')
        return redirect('academics:classe_list')
    return render(request, 'academics/classe_confirm_delete.html', {'classe': classe})


# ========== API (dropdowns dépendants) ==========
@login_required
def api_departements(request):
    faculte_id = request.GET.get('faculte_id')
    qs = Departement.objects.filter(active=True)
    if faculte_id:
        qs = qs.filter(faculte_id=faculte_id)
    data = [{'id': d.id, 'text': f"{d.code} — {d.nom}"} for d in qs.order_by('nom')]
    return JsonResponse({'results': data})


@login_required
def api_filieres(request):
    section_id = request.GET.get('section_id')
    departement_id = request.GET.get('departement_id')
    faculte_id = request.GET.get('faculte_id')
    qs = Filiere.objects.filter(active=True)
    if departement_id:
        qs = qs.filter(departement_id=departement_id)
    elif faculte_id:
        qs = qs.filter(faculte_id=faculte_id)
    if section_id:
        qs = qs.filter(section_id=section_id)
    data = [{'id': f.id, 'text': f"{f.code} - {f.nom}"} for f in qs.order_by('code')]
    return JsonResponse({'results': data})


@login_required
def api_promotions(request):
    filiere_id = request.GET.get('filiere_id')
    qs = Promotion.objects.filter(active=True)
    if filiere_id:
        qs = qs.filter(filiere_id=filiere_id)
    data = [{'id': p.id, 'text': p.nom} for p in qs.order_by('ordre', 'code')]
    return JsonResponse({'results': data})


@login_required
def api_classes(request):
    promotion_id = request.GET.get('promotion_id')
    qs = Classe.objects.filter(active=True).select_related('local')
    if promotion_id:
        qs = qs.filter(promotion_id=promotion_id)
    data = []
    for classe in qs.order_by('code'):
        texte = classe.nom or f"Classe {classe.code}"
        if classe.local_id:
            texte = f"{texte} ({classe.local.code})"
        data.append({'id': classe.id, 'text': texte})
    return JsonResponse({'results': data})


@login_required
def api_local(request):
    classe_id = request.GET.get('classe_id')
    if not classe_id:
        return JsonResponse({'local': None})
    try:
        classe = Classe.objects.select_related('local').get(pk=classe_id)
    except Classe.DoesNotExist:
        return JsonResponse({'local': None})
    if not classe.local_id:
        return JsonResponse({'local': None})
    return JsonResponse({'local': {'id': classe.local_id, 'code': classe.local.code, 'nom': classe.local.nom}})


# ========== SEMESTRES ==========
@login_required
def semestre_list(request):
    semestres = Semestre.objects.all().order_by('numero')
    paginator = Paginator(semestres, 10)
    page = request.GET.get('page')
    semestres = paginator.get_page(page)
    return render(request, 'academics/semestre_list.html', {'semestres': semestres})


@login_required
def semestre_create(request):
    if request.method == 'POST':
        form = SemestreForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Semestre créé avec succès!')
            return redirect('academics:semestre_list')
    else:
        form = SemestreForm()
    return render(request, 'academics/semestre_form.html', {'form': form, 'title': 'Nouveau Semestre'})


@login_required
def semestre_update(request, pk):
    semestre = get_object_or_404(Semestre, pk=pk)
    if request.method == 'POST':
        form = SemestreForm(request.POST, instance=semestre)
        if form.is_valid():
            form.save()
            messages.success(request, 'Semestre modifié avec succès!')
            return redirect('academics:semestre_list')
    else:
        form = SemestreForm(instance=semestre)
    return render(request, 'academics/semestre_form.html', {'form': form, 'title': 'Modifier Semestre', 'object': semestre})


@login_required
def semestre_delete(request, pk):
    semestre = get_object_or_404(Semestre, pk=pk)
    if request.method == 'POST':
        semestre.delete()
        messages.success(request, 'Semestre supprimé avec succès!')
        return redirect('academics:semestre_list')
    return render(request, 'academics/semestre_confirm_delete.html', {'semestre': semestre})


# ========== UNITES D'ENSEIGNEMENT ==========
@login_required
def ue_list(request):
    filter_form = UEListFilterForm(request.GET or None)
    ues = UniteEnseignement.objects.select_related('semestre', 'filiere').all()

    if filter_form.is_valid():
        semestre = filter_form.cleaned_data.get('semestre')
        if semestre:
            ues = ues.filter(semestre=semestre)
        filiere = filter_form.cleaned_data.get('filiere')
        if filiere:
            ues = ues.filter(filiere=filiere)

    ues = ues.order_by('semestre', 'filiere', 'ordre', 'code')
    paginator = Paginator(ues, 10)
    page = request.GET.get('page')
    ues = paginator.get_page(page)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    filter_query = query_params.urlencode()

    return render(request, 'academics/ue_list.html', {
        'ues': ues,
        'filter_form': filter_form,
        'filter_query': filter_query,
        'has_filters': any(query_params.values()),
    })


@login_required
def ue_create(request):
    if request.method == 'POST':
        form = UniteEnseignementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'UE créée avec succès!')
            return redirect('academics:ue_list')
    else:
        form = UniteEnseignementForm()
    return render(request, 'academics/ue_form.html', {'form': form, 'title': 'Nouvelle UE'})


@login_required
def ue_update(request, pk):
    ue = get_object_or_404(UniteEnseignement, pk=pk)
    if request.method == 'POST':
        form = UniteEnseignementForm(request.POST, instance=ue)
        if form.is_valid():
            form.save()
            messages.success(request, 'UE modifiée avec succès!')
            return redirect('academics:ue_list')
    else:
        form = UniteEnseignementForm(instance=ue)
    return render(request, 'academics/ue_form.html', {'form': form, 'title': 'Modifier UE', 'object': ue})


@login_required
def ue_delete(request, pk):
    ue = get_object_or_404(UniteEnseignement, pk=pk)
    if request.method == 'POST':
        ue.delete()
        messages.success(request, 'UE supprimée avec succès!')
        return redirect('academics:ue_list')
    return render(request, 'academics/ue_confirm_delete.html', {'ue': ue})


# ========== ELEMENTS CONSTITUTIFS ==========
@login_required
def ec_list(request):
    filter_form = UEListFilterForm(request.GET or None)

    ec_qs = ElementConstitutif.objects.select_related('professeur').order_by('ordre', 'code')
    ues = (
        UniteEnseignement.objects.select_related('semestre', 'filiere')
        .prefetch_related(Prefetch('ecs', queryset=ec_qs))
        .filter(ecs__isnull=False)
        .distinct()
    )

    if filter_form.is_valid():
        semestre = filter_form.cleaned_data.get('semestre')
        if semestre:
            ues = ues.filter(semestre=semestre)
        filiere = filter_form.cleaned_data.get('filiere')
        if filiere:
            ues = ues.filter(filiere=filiere)

    ues = ues.order_by('semestre', 'filiere', 'ordre', 'code')
    ec_total = ElementConstitutif.objects.filter(ue__in=ues).count()

    paginator = Paginator(ues, 10)
    page = request.GET.get('page')
    ues = paginator.get_page(page)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    filter_query = query_params.urlencode()

    return render(request, 'academics/ec_list.html', {
        'ues': ues,
        'ec_total': ec_total,
        'filter_form': filter_form,
        'filter_query': filter_query,
        'has_filters': any(query_params.values()),
    })


@login_required
def ec_create(request):
    if request.method == 'POST':
        form = ElementConstitutifForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'EC créé avec succès!')
            return redirect('academics:ec_list')
    else:
        form = ElementConstitutifForm()
    return render(request, 'academics/ec_form.html', {'form': form, 'title': 'Nouvel EC'})


@login_required
def ec_update(request, pk):
    ec = get_object_or_404(ElementConstitutif, pk=pk)
    if request.method == 'POST':
        form = ElementConstitutifForm(request.POST, instance=ec)
        if form.is_valid():
            form.save()
            messages.success(request, 'EC modifié avec succès!')
            return redirect('academics:ec_list')
    else:
        form = ElementConstitutifForm(instance=ec)
    return render(request, 'academics/ec_form.html', {'form': form, 'title': 'Modifier EC', 'object': ec})


@login_required
def ec_delete(request, pk):
    ec = get_object_or_404(ElementConstitutif, pk=pk)
    if request.method == 'POST':
        ec.delete()
        messages.success(request, 'EC supprimé avec succès!')
        return redirect('academics:ec_list')
    return render(request, 'academics/ec_confirm_delete.html', {'ec': ec})
