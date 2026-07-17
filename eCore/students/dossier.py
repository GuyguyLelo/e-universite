"""Synchronisation automatique de la complétude des dossiers."""

from .models import DossierEtudiant, DocumentEtudiant, Inscription, TypeDocument


def documents_obligatoires_deposes(inscription):
    """Types obligatoires actifs marqués comme déposés pour cette inscription."""
    obligatoires = TypeDocument.objects.filter(obligatoire=True, active=True)
    obligatoires_ids = set(obligatoires.values_list('id', flat=True))
    if not obligatoires_ids:
        return True, obligatoires_ids, set()

    deposes = DocumentEtudiant.objects.filter(
        inscription=inscription,
        type_document_id__in=obligatoires_ids,
    )

    types_deposes = set(deposes.values_list('type_document_id', flat=True))
    complet = obligatoires_ids.issubset(types_deposes)
    return complet, obligatoires_ids, types_deposes


def build_dossier_checklist(inscription):
    """Liste des types de documents actifs avec état de dépôt."""
    types = TypeDocument.objects.filter(active=True).order_by('ordre', 'nom')
    existing = {
        doc.type_document_id: doc
        for doc in DocumentEtudiant.objects.filter(inscription=inscription).select_related('type_document')
    }
    checklist = []
    for type_doc in types:
        document = existing.get(type_doc.pk)
        checklist.append({
            'type': type_doc,
            'depose': document is not None,
            'document': document,
        })
    return checklist


def sync_inscription_dossier(inscription):
    """Recalcule dossier_complet et le statut du dossier administratif."""
    if isinstance(inscription, int):
        inscription = Inscription.objects.get(pk=inscription)

    dossier, _ = DossierEtudiant.objects.get_or_create(inscription=inscription)
    return dossier.verifier_completude()


def sync_document_dossiers(document):
    """Met à jour le dossier lié à l'inscription du document."""
    if document.inscription_id:
        sync_inscription_dossier(document.inscription_id)
