"""
Crée les enseignants des horaires comme personnel (catégorie Enseignant)
et rattache les lignes d'horaire / EC correspondants.

Usage:
  python manage.py import_enseignants_horaire
  python manage.py import_enseignants_horaire --dry-run
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import ElementConstitutif
from cards.models import Category, Personnel, Position
from prestation.models import HoraireLigne

ENSEIGNANT_CATEGORY = "Enseignant"
ENSEIGNANT_POSITION = "Enseignant"


def parse_nom_prenom(full_name):
    """Format horaire : NOM PRENOM(S)."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], "—"
    return parts[0], " ".join(parts[1:])


def display_name(last_name, first_name):
    first = (first_name or "").strip()
    if first in ("", "—"):
        return last_name.strip()
    return f"{last_name} {first}".strip()


class Command(BaseCommand):
    help = "Intègre les enseignants des horaires dans le module Personnel."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les actions sans enregistrer",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        category = Category.objects.filter(name=ENSEIGNANT_CATEGORY).first()
        if not category:
            self.stderr.write(self.style.ERROR(
                f"Catégorie « {ENSEIGNANT_CATEGORY} » introuvable. "
                "Exécutez : python manage.py seed_personnel_categories"
            ))
            return

        names = sorted({
            line.titulaire_affichage.strip()
            for line in HoraireLigne.objects.all()
            if line.titulaire_affichage and line.titulaire_affichage != "-"
        })

        if not names:
            self.stderr.write(self.style.WARNING("Aucun enseignant trouvé dans les horaires."))
            return

        position = Position.objects.filter(name=ENSEIGNANT_POSITION).first()
        if not position and not dry_run:
            position, _ = Position.objects.get_or_create(name=ENSEIGNANT_POSITION)

        created_count = 0
        updated_count = 0
        linked_lines = 0
        linked_ecs = 0
        personnel_by_display = {}

        with transaction.atomic():
            year = date.today().year
            next_seq = (Personnel.objects.order_by("-id").values_list("id", flat=True).first() or 0) + 1

            for full_name in names:
                last_name, first_name = parse_nom_prenom(full_name)
                if not last_name:
                    continue

                personnel = Personnel.objects.filter(
                    last_name__iexact=last_name,
                    first_name__iexact=first_name,
                ).first()

                defaults = {
                    "category": category,
                    "position": position,
                    "function_quality": ENSEIGNANT_POSITION,
                    "education_level": "Non renseigné",
                    "contract_type": "vacataire",
                    "assignment_service": "DSI — Division Formation",
                    "nationality": "Congolaise",
                }

                if personnel:
                    for field, value in defaults.items():
                        setattr(personnel, field, value)
                    if not personnel.matricule:
                        personnel.matricule = f"MAT-{year}-{next_seq:04d}"
                        next_seq += 1
                    if not dry_run:
                        personnel.save()
                    updated_count += 1
                else:
                    personnel = Personnel(
                        last_name=last_name,
                        first_name=first_name,
                        matricule=f"MAT-{year}-{next_seq:04d}",
                        **defaults,
                    )
                    next_seq += 1
                    if not dry_run:
                        personnel.save()
                    created_count += 1

                personnel_by_display[full_name.upper()] = personnel
                self.stdout.write(f"  {display_name(last_name, first_name)} ({personnel.matricule if personnel.pk or not dry_run else 'nouveau'})")

            for line in HoraireLigne.objects.select_related("element_constitutif").all():
                label = (line.titulaire_affichage or "").strip().upper()
                if not label or label == "-":
                    continue
                personnel = personnel_by_display.get(label)
                if not personnel:
                    continue
                if dry_run:
                    linked_lines += 1
                    if line.element_constitutif_id:
                        linked_ecs += 1
                    continue
                line.professeur = personnel
                line.save(update_fields=["professeur", "updated_at"])
                linked_lines += 1
                if line.element_constitutif_id:
                    ec = line.element_constitutif
                    if ec.professeur_id != personnel.id:
                        ec.professeur = personnel
                        ec.save(update_fields=["professeur", "updated_at"])
                        linked_ecs += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[Simulation] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{created_count} enseignant(s) créé(s), "
            f"{updated_count} mis à jour, "
            f"{linked_lines} ligne(s) d'horaire liée(s), "
            f"{linked_ecs} EC mis à jour."
        ))
