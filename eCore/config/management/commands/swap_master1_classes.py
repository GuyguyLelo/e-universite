"""
Inverse les classes PMC/PMR pour les listes Master 1 CSI et RX.
Utile si l'import initial a rattaché chaque liste à la mauvaise promotion.
"""
from django.core.management.base import BaseCommand

from config.management.commands.fix_master1_filiere import Command as FixCommand


class Command(BaseCommand):
    help = "Inverse CSI->PMR et RX->PMC pour les etudiants Master 1."

    def handle(self, *args, **options):
        options["swap_classes"] = True
        FixCommand().handle(*args, **options)
