from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .dossier import sync_document_dossiers
from .models import DocumentEtudiant


@receiver(post_save, sender=DocumentEtudiant)
def document_etudiant_saved(sender, instance, **kwargs):
    sync_document_dossiers(instance)


@receiver(post_delete, sender=DocumentEtudiant)
def document_etudiant_deleted(sender, instance, **kwargs):
    sync_document_dossiers(instance)
