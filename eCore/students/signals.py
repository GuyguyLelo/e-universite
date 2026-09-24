from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .compte import assurer_compte_etudiant
from .dossier import sync_document_dossiers
from .models import DocumentEtudiant, Inscription, Student


@receiver(post_save, sender=DocumentEtudiant)
def document_etudiant_saved(sender, instance, **kwargs):
    sync_document_dossiers(instance)


@receiver(post_delete, sender=DocumentEtudiant)
def document_etudiant_deleted(sender, instance, **kwargs):
    sync_document_dossiers(instance)


@receiver(post_save, sender=Student)
def student_compte_personnel(sender, instance, **kwargs):
    assurer_compte_etudiant(instance)


@receiver(post_save, sender=Inscription)
def inscription_compte_personnel(sender, instance, **kwargs):
    if instance.statut in {"desinscrit", "abandon"}:
        return
    assurer_compte_etudiant(instance.etudiant)
