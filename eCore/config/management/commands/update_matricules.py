"""
Attribue les matricules étudiants : année + n° d'ordre (ex. 20260001),
sans distinction de filière.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique
from students.matricule import (
    MATRICULE_HELP,
    apply_matricule_assignments,
    build_matricule_assignments,
    matricule_year_default,
)


class Command(BaseCommand):
    help = f"Met à jour les matricules étudiants inscrits sur l'année. {MATRICULE_HELP}"

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee-academique',
            help="Code année académique (ex. 2024-2025). Par défaut : année active.",
        )
        parser.add_argument(
            '--annee',
            type=int,
            help="Année dans le matricule (ex. 2026). Par défaut : année de fin de l'année active.",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche les changements sans enregistrer.",
        )
        parser.add_argument(
            '--update-email',
            action='store_true',
            help="Met à jour l'email étudiant selon le nouveau matricule.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['annee_academique']:
            annee = AnneeAcademique.objects.filter(code=options['annee_academique']).first()
        else:
            annee = AnneeAcademique.get_active()
        if not annee:
            self.stderr.write(self.style.ERROR("Année académique introuvable."))
            return

        year = options['annee'] or matricule_year_default(annee)
        assignments = build_matricule_assignments(annee, year=year)

        if not assignments:
            self.stderr.write(self.style.WARNING(
                "Aucun étudiant inscrit sur cette année."
            ))
            return

        if options['dry_run']:
            for student, numero in assignments[:8]:
                self.stdout.write(f"  {student.numero_etudiant} -> {numero}  ({student.nom})")
            if len(assignments) > 8:
                self.stdout.write(f"  … et {len(assignments) - 8} autre(s)")
            self.stdout.write(
                self.style.WARNING(
                    f"Simulation — {len(assignments)} matricule(s) (format {year}####)."
                )
            )
            return

        updated = apply_matricule_assignments(
            assignments,
            update_email=options['update_email'],
        )

        self.stdout.write(self.style.SUCCESS(
            f"{updated} matricule(s) mis à jour (format {year}####)."
        ))
        for student, numero in assignments[:5]:
            self.stdout.write(f"  {numero}  {student.prenom} {student.nom}")
        if len(assignments) > 5:
            self.stdout.write("  …")
