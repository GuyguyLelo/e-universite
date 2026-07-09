"""
Vues pour la génération de documents
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from io import BytesIO

from students.models import Student, Inscription
from academics.models import Semestre, Filiere, Promotion, AnneeAcademique
from academics.utils import NO_ACTIVE_ANNEE_ERROR
from evaluations.models import Session
from deliberations.models import Deliberation
from deliberations.access import user_can_access_deliberation
from documents.models import DocumentGenere, TypeDocumentGenere, Attestation, TypeAttestation
from documents.forms import AttestationForm, AttestationListFilterForm
from documents.services import (
    ReleveNotesGenerator,
    ProcesVerbalGenerator,
    AttestationGenerator,
    generer_attestation_pdf,
    enregistrer_grille_notes_pdf,
)


def _document_selection_from_get(request, include_etudiant=False):
    """Extrait les sélections du formulaire GET pour pré-remplir les listes."""
    selected = {}
    mapping = {
        'semestre': request.GET.get('semestre'),
        'option': request.GET.get('option'),
        'promotion': request.GET.get('promotion'),
        'session': request.GET.get('session'),
    }
    if include_etudiant:
        mapping['etudiant'] = request.GET.get('etudiant')
    for key, value in mapping.items():
        if value and value.isdigit():
            selected[key] = int(value)
    return selected


@login_required
def generate_releve_notes(request, etudiant_id, session_id):
    """Génère un relevé de notes pour un étudiant"""
    etudiant = get_object_or_404(Student, id=etudiant_id)
    session = get_object_or_404(Session, id=session_id)
    
    # Générer le PDF
    buffer = BytesIO()
    generator = ReleveNotesGenerator(etudiant, session, buffer)
    generator.generate()
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="releve_notes_{etudiant.numero_etudiant}_{session.code}.pdf"'
    
    # Sauvegarder le document généré
    type_doc, created = TypeDocumentGenere.objects.get_or_create(
        code='RELEVE_NOTES',
        defaults={'nom': 'Relevé de notes', 'active': True}
    )
    
    DocumentGenere.objects.create(
        type_document=type_doc,
        etudiant=etudiant,
        session=session,
        fichier=f'releve_notes_{etudiant.numero_etudiant}_{session.code}.pdf',
        genere_par=request.user
    )
    
    return response


@login_required
def generate_proces_verbal(request, deliberation_id):
    """Génère un procès-verbal de délibération"""
    deliberation = get_object_or_404(Deliberation, id=deliberation_id)
    if not user_can_access_deliberation(request.user, deliberation):
        raise Http404
    
    # Générer le PDF
    buffer = BytesIO()
    generator = ProcesVerbalGenerator(deliberation, buffer)
    generator.generate()
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="proces_verbal_{deliberation.session.code}.pdf"'
    
    # Sauvegarder le document généré
    type_doc, created = TypeDocumentGenere.objects.get_or_create(
        code='PROCES_VERBAL',
        defaults={'nom': 'Procès-verbal de délibération', 'active': True}
    )
    
    DocumentGenere.objects.create(
        type_document=type_doc,
        deliberation=deliberation,
        session=deliberation.session,
        fichier=f'proces_verbal_{deliberation.session.code}.pdf',
        genere_par=request.user
    )
    
    return response


@login_required
def generate_attestation(request, inscription_id, type_attestation='scolarite'):
    """Génère une attestation (URL historique — crée un enregistrement si besoin)."""
    inscription = get_object_or_404(Inscription, id=inscription_id)
    type_obj = TypeAttestation.objects.filter(code=type_attestation, active=True).first()
    if not type_obj:
        type_obj = TypeAttestation.objects.filter(active=True).order_by('ordre').first()
    if not type_obj:
        messages.error(request, "Aucun type d'attestation configuré.")
        return redirect('documents:attestation_list')

    attestation = Attestation.objects.create(
        inscription=inscription,
        type_attestation=type_obj,
        date_delivrance=timezone.localdate(),
        lieu_delivrance='Brazzaville',
    )
    return attestation_pdf(request, attestation.pk)


# ========== GRILLE DE NOTES ==========
@login_required
def grille_notes(request):
    """
    Page de sélection des paramètres pour générer la grille de notes PDF.
    Si les paramètres sont déjà dans la query string, génère et renvoie le PDF directement.
    """
    semestre_id = request.GET.get('semestre')
    filiere_id = request.GET.get('option')
    promotion_id = request.GET.get('promotion')
    session_id = request.GET.get('session')

    if all([semestre_id, filiere_id, promotion_id, session_id]):
        annee = AnneeAcademique.get_active()
        if not annee:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            semestre = get_object_or_404(Semestre, pk=semestre_id)
            filiere = get_object_or_404(Filiere, pk=filiere_id)
            promotion = get_object_or_404(Promotion, pk=promotion_id)
            session = get_object_or_404(Session, pk=session_id, semestre=semestre)

            _, pdf_bytes = enregistrer_grille_notes_pdf(
                semestre, filiere, promotion, annee, session, genere_par=request.user,
            )
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="grille_notes_{semestre.code}_{promotion.code}_{session.code}_{annee.code}.pdf"'
            )
            return response

    sessions = Session.pour_annee(AnneeAcademique.get_active()).filter(active=True).select_related(
        'semestre', 'annee_academique',
    ).order_by('semestre__numero', 'numero')
    context = {
        'semestres': Semestre.objects.filter(active=True).order_by('numero'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'promotions': Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre'),
        'sessions': sessions,
        'selected': _document_selection_from_get(request),
    }
    return render(request, 'documents/grille_notes.html', context)


# ========== RELEVÉ DE NOTES ==========
def _inscriptions_pour_releve(promotion_id, filiere_id=None):
    """Inscriptions actives de la promotion pour l'année académique en cours."""
    annee = AnneeAcademique.get_active()
    if not annee or not promotion_id:
        return Inscription.objects.none(), annee

    qs = (
        Inscription.objects.filter(
            annee_academique=annee,
            classe__promotion_id=promotion_id,
        )
        .eligibles_listes()
        .select_related('etudiant', 'classe', 'classe__promotion', 'classe__promotion__filiere')
        .order_by('etudiant__numero_etudiant')
    )
    if filiere_id:
        qs = qs.filter(classe__promotion__filiere_id=filiere_id)
    return qs, annee


@login_required
def releve_notes_selection(request):
    """Page de sélection pour générer un relevé de notes PDF"""
    semestre_id = request.GET.get('semestre')
    filiere_id = request.GET.get('option')
    promotion_id = request.GET.get('promotion')
    etudiant_id = request.GET.get('etudiant')

    if all([semestre_id, filiere_id, promotion_id, etudiant_id]):
        annee = AnneeAcademique.get_active()
        if not annee:
            messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        else:
            semestre = get_object_or_404(Semestre, pk=semestre_id)
            filiere = get_object_or_404(Filiere, pk=filiere_id)
            promotion = get_object_or_404(Promotion, pk=promotion_id)
            etudiant = get_object_or_404(Student, pk=etudiant_id)

            buffer = BytesIO()
            generator = ReleveNotesGenerator(etudiant, semestre, filiere, promotion, annee, buffer)
            generator.generate()
            buffer.seek(0)
            response = HttpResponse(buffer.read(), content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="releve_notes_{etudiant.numero_etudiant}_{semestre.code}.pdf"'
            )
            return response

    selected = _document_selection_from_get(request, include_etudiant=True)
    inscriptions_promotion = Inscription.objects.none()
    if selected.get('promotion'):
        filiere_pk = selected.get('option')
        inscriptions_promotion, _ = _inscriptions_pour_releve(
            selected['promotion'],
            filiere_pk,
        )

    context = {
        'semestres': Semestre.objects.filter(active=True).order_by('numero'),
        'filieres': Filiere.objects.filter(active=True).order_by('code'),
        'promotions': Promotion.objects.filter(active=True).select_related('filiere').order_by('filiere', 'ordre'),
        'inscriptions_promotion': inscriptions_promotion,
        'selected': selected,
    }
    return render(request, 'documents/releve_notes.html', context)


# ========== ATTESTATIONS ==========
@login_required
def attestation_list(request):
    annee = AnneeAcademique.get_active()
    filter_form = AttestationListFilterForm(request.GET or None, annee=annee)
    type_attestation = None

    inscriptions_qs = (
        Inscription.objects.filter(classe__isnull=False)
        .eligibles_listes()
        .select_related(
            'etudiant',
            'classe',
            'classe__promotion',
            'classe__promotion__filiere',
            'annee_academique',
        )
        .order_by(
            'classe__promotion__filiere__code',
            'classe__promotion__ordre',
            'classe__code',
            'etudiant__nom',
            'etudiant__prenom',
        )
    )
    if annee:
        inscriptions_qs = inscriptions_qs.filter(annee_academique=annee)
    else:
        inscriptions_qs = inscriptions_qs.none()
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)

    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        if q:
            terme = q.strip()
            inscriptions_qs = inscriptions_qs.filter(
                Q(etudiant__numero_etudiant__icontains=terme)
                | Q(etudiant__nom__icontains=terme)
                | Q(etudiant__prenom__icontains=terme)
            )
        filiere = filter_form.cleaned_data.get('filiere')
        if filiere:
            inscriptions_qs = inscriptions_qs.filter(classe__promotion__filiere=filiere)
        promotion = filter_form.cleaned_data.get('promotion')
        if promotion:
            inscriptions_qs = inscriptions_qs.filter(classe__promotion=promotion)
        classe = filter_form.cleaned_data.get('classe')
        if classe:
            inscriptions_qs = inscriptions_qs.filter(classe=classe)
        type_attestation = filter_form.cleaned_data.get('type_attestation')

    attestation_qs = (
        Attestation.objects.select_related('type_attestation')
        .order_by('-date_delivrance', '-created_at')
    )
    if type_attestation:
        attestation_qs = attestation_qs.filter(type_attestation=type_attestation)

    inscriptions_qs = inscriptions_qs.prefetch_related(
        Prefetch('attestations', queryset=attestation_qs),
    )

    lignes = []
    for inscription in inscriptions_qs:
        attestations = list(inscription.attestations.all())
        lignes.append({
            'inscription': inscription,
            'etudiant': inscription.etudiant,
            'derniere_attestation': attestations[0] if attestations else None,
            'nb_attestations': len(attestations),
        })

    filter_query = request.GET.copy()
    filter_query.pop('page', None)
    has_filters = any(v for k, v in filter_query.items() if v)

    paginator = Paginator(lignes, 25)
    etudiants_page = paginator.get_page(request.GET.get('page'))

    return render(request, 'documents/attestation_list.html', {
        'annee': annee,
        'etudiants': etudiants_page,
        'type_attestation': type_attestation,
        'filter_form': filter_form,
        'has_filters': has_filters,
        'filter_query': filter_query.urlencode(),
    })


@login_required
def attestation_create(request):
    annee = AnneeAcademique.get_active()
    if not annee:
        messages.error(request, NO_ACTIVE_ANNEE_ERROR)
        return redirect('documents:attestation_list')

    if request.method == 'POST':
        form = AttestationForm(request.POST, annee=annee)
        if form.is_valid():
            attestation = form.save()
            messages.success(request, 'Attestation enregistrée. Vous pouvez générer le PDF.')
            if 'generer_pdf' in request.POST:
                return redirect('documents:attestation_pdf', pk=attestation.pk)
            return redirect('documents:attestation_list')
    else:
        form = AttestationForm(annee=annee)
        inscription_id = request.GET.get('inscription')
        if inscription_id and inscription_id.isdigit():
            form.fields['inscription'].initial = int(inscription_id)
        type_id = request.GET.get('type_attestation')
        if type_id and type_id.isdigit():
            form.fields['type_attestation'].initial = int(type_id)
    return render(request, 'documents/attestation_form.html', {
        'form': form,
        'title': 'Nouvelle attestation',
        'annee': annee,
    })


@login_required
def attestation_update(request, pk):
    attestation = get_object_or_404(Attestation, pk=pk)
    annee = attestation.inscription.annee_academique
    if request.method == 'POST':
        form = AttestationForm(request.POST, instance=attestation, annee=annee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attestation mise à jour.')
            if 'generer_pdf' in request.POST:
                return redirect('documents:attestation_pdf', pk=attestation.pk)
            return redirect('documents:attestation_list')
    else:
        form = AttestationForm(instance=attestation, annee=annee)
    return render(request, 'documents/attestation_form.html', {
        'form': form,
        'title': 'Modifier attestation',
        'object': attestation,
        'annee': annee,
    })


@login_required
def attestation_delete(request, pk):
    attestation = get_object_or_404(Attestation, pk=pk)
    if request.method == 'POST':
        if attestation.fichier:
            attestation.fichier.delete(save=False)
        attestation.delete()
        messages.success(request, 'Attestation supprimée.')
        return redirect('documents:attestation_list')
    return render(request, 'documents/attestation_confirm_delete.html', {
        'attestation': attestation,
    })


@login_required
def attestation_pdf(request, pk):
    """Génère ou affiche le PDF d'une attestation."""
    attestation = get_object_or_404(
        Attestation.objects.select_related(
            'type_attestation',
            'inscription',
            'inscription__etudiant',
            'inscription__classe',
            'inscription__annee_academique',
        ),
        pk=pk,
    )
    pdf_bytes, filename = generer_attestation_pdf(attestation, genere_par=request.user)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
