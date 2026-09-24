from decimal import Decimal

from django.db.models import Exists, OuterRef, Q, Sum

from academics.models import ElementConstitutif
from evaluations.calcul_notes import etudiant_convoque_rattrapage, note_exam_etudiant_sur_10
from evaluations.models import Session
from evaluations.session_workflow import _evaluations_exam_session_principale

from .models import ConfirmationPaiement, MotifPaiement, Paiement


def _semestre_id(semestre):
    if semestre is None:
        return None
    return semestre.pk if hasattr(semestre, 'pk') else semestre


def filieres_enrollement_q():
    return Q(classe__promotion__filiere__isnull=False)


def inscription_eligible_enrollement(inscription) -> bool:
    if not inscription.classe_id:
        return False
    promotion = getattr(inscription.classe, 'promotion', None)
    filiere = getattr(promotion, 'filiere', None)
    return filiere is not None


def inscription_convoquee_rattrapage(inscription, semestre) -> bool:
    """True si l'étudiant a au moins un examen < 10/10 en session principale du semestre."""
    if not inscription_eligible_enrollement(inscription):
        return False

    semestre_id = _semestre_id(semestre)
    s1 = Session.objects.filter(
        semestre_id=semestre_id,
        numero=1,
        active=True,
        annee_academique_id=inscription.annee_academique_id,
    ).first()
    if not s1:
        return False

    filiere_id = inscription.classe.promotion.filiere_id
    etudiant = inscription.etudiant
    ecs = ElementConstitutif.objects.filter(
        ue__semestre_id=semestre_id,
        ue__filiere_id=filiere_id,
        active=True,
    )

    for ec in ecs:
        evaluations = _evaluations_exam_session_principale(ec, s1)
        if not evaluations.exists():
            continue
        note_exam = note_exam_etudiant_sur_10(etudiant, evaluations)
        if etudiant_convoque_rattrapage(note_exam):
            return True
    return False


def motifs_requis_inscription(inscription, *, semestre=None):
    """
    Motifs obligatoires pour une inscription et un semestre :
    - session principale (tous) ;
    - session rattrapage (uniquement si convoqué : examen < 10/10).
    """
    if not inscription_eligible_enrollement(inscription) or not semestre:
        return MotifPaiement.objects.none()

    semestre_id = _semestre_id(semestre)
    base = MotifPaiement.objects.filter(
        annee_academique_id=inscription.annee_academique_id,
        semestre_id=semestre_id,
        active=True,
    )

    filtres = Q(contexte=MotifPaiement.CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE)
    if inscription_convoquee_rattrapage(inscription, semestre):
        filtres |= Q(contexte=MotifPaiement.CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE)

    return base.filter(filtres)


def _motif_confirme(inscription, semestre_id, contexte) -> bool:
    return ConfirmationPaiement.objects.filter(
        inscription=inscription,
        confirme=True,
        motif_paiement__active=True,
        motif_paiement__annee_academique_id=inscription.annee_academique_id,
        motif_paiement__semestre_id=semestre_id,
        motif_paiement__contexte=contexte,
    ).exists()


def _calcule_en_ordre_semestre(inscription, semestre) -> bool:
    motifs = motifs_requis_inscription(inscription, semestre=semestre)
    motifs_ids = list(motifs.values_list('pk', flat=True))
    if not motifs_ids:
        return False

    confirmes = ConfirmationPaiement.objects.filter(
        inscription=inscription,
        confirme=True,
        motif_paiement_id__in=motifs_ids,
    ).count()
    return confirmes >= len(motifs_ids)


def calcule_en_ordre_paiement(inscription, *, semestre=None) -> bool:
    """Tous les motifs requis confirmés (un semestre ou tous les semestres configurés)."""
    if not inscription_eligible_enrollement(inscription):
        return False

    if semestre is not None:
        return _calcule_en_ordre_semestre(inscription, semestre)

    semestre_ids = (
        MotifPaiement.objects.filter(
            annee_academique_id=inscription.annee_academique_id,
            active=True,
        )
        .values_list('semestre_id', flat=True)
        .distinct()
    )
    semestre_ids = [sid for sid in semestre_ids if sid]
    if not semestre_ids:
        return False

    from academics.models import Semestre

    for semestre_id in semestre_ids:
        semestre_obj = Semestre.objects.filter(pk=semestre_id).first()
        if semestre_obj and not _calcule_en_ordre_semestre(inscription, semestre_obj):
            return False
    return True


def filtrer_inscriptions_en_ordre_paiement(queryset, semestre=None, session=None):
    """
    Inscriptions éligibles à la grille : enrôlement session principale confirmé ;
    si session rattrapage, les convoqués doivent aussi avoir payé le rattrapage.
    """
    semestre_id = _semestre_id(semestre)
    if not semestre_id:
        return queryset.none()

    session_numero = getattr(session, 'numero', None) or 1

    queryset = queryset.filter(classe__isnull=False).filter(filieres_enrollement_q())

    principale_confirme = ConfirmationPaiement.objects.filter(
        inscription_id=OuterRef('pk'),
        confirme=True,
        motif_paiement__active=True,
        motif_paiement__annee_academique_id=OuterRef('annee_academique_id'),
        motif_paiement__semestre_id=semestre_id,
        motif_paiement__contexte=MotifPaiement.CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE,
    )

    motifs_principale_exist = MotifPaiement.objects.filter(
        annee_academique_id=OuterRef('annee_academique_id'),
        semestre_id=semestre_id,
        active=True,
        contexte=MotifPaiement.CONTEXTE_ENROLLEMENT_SESSION_PRINCIPALE,
    )

    queryset = queryset.annotate(
        _a_motif_principale=Exists(motifs_principale_exist),
        _principale_confirmee=Exists(principale_confirme),
    ).filter(_a_motif_principale=True, _principale_confirmee=True)

    if session_numero != 2:
        return queryset

    ids_ok = []
    for inscription in queryset.select_related('etudiant', 'classe__promotion__filiere'):
        if inscription_convoquee_rattrapage(inscription, semestre):
            if not _motif_confirme(
                inscription,
                semestre_id,
                MotifPaiement.CONTEXTE_ENROLLEMENT_SESSION_RATTRAPAGE,
            ):
                continue
        ids_ok.append(inscription.pk)
    return queryset.filter(pk__in=ids_ok)


def sync_inscription_en_ordre_paiement(inscription):
    """Met à jour en_ordre_paiement selon tous les semestres configurés."""
    en_ordre = calcule_en_ordre_paiement(inscription)
    if inscription.en_ordre_paiement != en_ordre:
        inscription.en_ordre_paiement = en_ordre
        inscription.save(update_fields=['en_ordre_paiement', 'updated_at'])
    return en_ordre


def attach_confirmation_status(inscriptions, motif):
    """Ajoute motif_confirme, motifs_complets et compteurs sur chaque inscription."""
    if not motif:
        for inscription in inscriptions:
            inscription.motif_confirme = False
            inscription.motifs_complets = False
            inscription.motifs_confirmes_count = 0
            inscription.motifs_total_count = 0
            inscription.convoque_rattrapage = False
        return

    inscription_ids = [ins.pk for ins in inscriptions]
    confirmes_motif = set(
        ConfirmationPaiement.objects.filter(
            inscription_id__in=inscription_ids,
            motif_paiement_id=motif.pk,
            confirme=True,
        ).values_list('inscription_id', flat=True)
    )

    for inscription in inscriptions:
        inscription.motif_confirme = inscription.pk in confirmes_motif
        inscription.convoque_rattrapage = inscription_convoquee_rattrapage(
            inscription,
            motif.semestre,
        )
        motifs_requis = motifs_requis_inscription(inscription, semestre=motif.semestre)
        motifs_ids = list(motifs_requis.values_list('pk', flat=True))
        motifs_total = len(motifs_ids)
        inscription.motifs_total_count = motifs_total
        if motifs_total == 0:
            inscription.motifs_confirmes_count = 0
            inscription.motifs_complets = False
            continue
        confirmes = ConfirmationPaiement.objects.filter(
            inscription=inscription,
            confirme=True,
            motif_paiement_id__in=motifs_ids,
        ).count()
        inscription.motifs_confirmes_count = confirmes
        inscription.motifs_complets = confirmes >= motifs_total


def total_paye(inscription, motif, devise=None):
    """Somme des paiements au statut Payé pour une inscription et un frais."""
    qs = Paiement.objects.filter(
        inscription=inscription,
        motif_paiement=motif,
        statut=Paiement.STATUT_PAYE,
    )
    if devise:
        qs = qs.filter(devise=devise)
    return qs.aggregate(total=Sum('montant'))['total'] or Decimal('0')


def frais_couvert(inscription, motif) -> bool:
    """Le frais est soldé dès qu'un paiement variable est encaissé, ou que le montant requis est atteint."""
    if motif.montant and motif.montant > 0:
        return total_paye(inscription, motif, devise=motif.devise) >= motif.montant
    return Paiement.objects.filter(
        inscription=inscription,
        motif_paiement=motif,
        statut=Paiement.STATUT_PAYE,
    ).exists()


def synchroniser_confirmation_depuis_paiements(inscription, motif, user=None):
    """
    Aligne la confirmation d'enrôlement sur les paiements enregistrés.
    Sans aucun paiement, la confirmation manuelle (étudiant en ordre) est conservée.
    """
    if not Paiement.objects.filter(inscription=inscription, motif_paiement=motif).exists():
        return sync_inscription_en_ordre_paiement(inscription)

    confirme = frais_couvert(inscription, motif)
    confirmation, created = ConfirmationPaiement.objects.get_or_create(
        inscription=inscription,
        motif_paiement=motif,
        defaults={'confirme': confirme, 'confirme_par': user},
    )
    if not created and confirmation.confirme != confirme:
        confirmation.confirme = confirme
        confirmation.confirme_par = user
        confirmation.save(update_fields=['confirme', 'confirme_par', 'date_confirmation', 'updated_at'])
    return sync_inscription_en_ordre_paiement(inscription)


def motifs_actifs(annee_academique_id=None, contexte=None, semestre_id=None):
    qs = MotifPaiement.objects.filter(active=True)
    if annee_academique_id:
        qs = qs.filter(annee_academique_id=annee_academique_id)
    if contexte:
        qs = qs.filter(contexte=contexte)
    if semestre_id:
        qs = qs.filter(semestre_id=semestre_id)
    return qs
