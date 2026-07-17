"""
Renseigne le bureau du jury M1 CSI/RX (2025-2026) sur les délibérations existantes.

Usage:
  python manage.py seed_jury_bureau_m1_2526
  python manage.py seed_jury_bureau_m1_2526 --force
  python manage.py seed_jury_bureau_m1_2526 --annee 2025-2026
"""
from django.core.management.base import BaseCommand

from academics.models import AnneeAcademique, Promotion
from deliberations.constants import ANNEE_JURY_M1_DEFAUT, FILIERES_JURY_M1_DEFAUT
from deliberations.jury_bureau import appliquer_jury_m1_defaut_sur_deliberation
from deliberations.models import Deliberation


class Command(BaseCommand):
    help = (
        "Insère la composition du bureau du jury M1 CSI/RX "
        "(Président, Secrétaire, Membres) sur les délibérations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee',
            default=ANNEE_JURY_M1_DEFAUT,
            help=f"Code année académique (défaut : {ANNEE_JURY_M1_DEFAUT})",
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Écrase les noms déjà renseignés',
        )

    def handle(self, *args, **options):
        annee_code = options['annee']
        force = options['force']
        annee = AnneeAcademique.objects.filter(code=annee_code).first()

        promotions = Promotion.objects.filter(
            filiere__code__in=FILIERES_JURY_M1_DEFAUT,
            active=True,
        ).select_related('filiere').order_by('filiere__code', 'code')

        if not promotions.exists():
            self.stderr.write(self.style.ERROR('Aucune promotion CSI/RX trouvée.'))
            return

        deliberations = Deliberation.objects.filter(
            promotion__in=promotions,
        ).select_related('promotion', 'promotion__filiere', 'session', 'session__annee_academique')

        if annee:
            deliberations = deliberations.filter(
                models_q_annee(annee),
            )

        updated = 0
        for deliberation in deliberations.order_by('promotion__filiere__code', 'promotion__code'):
            if appliquer_jury_m1_defaut_sur_deliberation(deliberation, force=force):
                updated += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  -> {deliberation.promotion.code} ({deliberation.promotion.filiere.code}) "
                    f"- {deliberation.libelle_court}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"Bureau du jury renseigné sur {updated} délibération(s) "
            f"(CSI/RX, année {annee_code})."
        ))


def models_q_annee(annee):
    from django.db.models import Q
    return (
        Q(session__annee_academique=annee)
        | Q(annee_academique=annee)
        | Q(annee_academique_m1=annee)
    )
