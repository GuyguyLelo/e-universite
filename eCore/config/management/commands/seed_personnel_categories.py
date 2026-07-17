"""
Crée les catégories officielles du personnel.
Usage: python manage.py seed_personnel_categories
"""
from django.core.management.base import BaseCommand

from cards.models import Category

PERSONNEL_CATEGORIES = [
    "Enseignant",
    "Personnel Administratif",
    "Personnel technique",
    "Autres",
]


class Command(BaseCommand):
    help = "Intègre les catégories du personnel (enseignant, administratif, technique, autres)."

    def handle(self, *args, **options):
        created = 0
        for name in PERSONNEL_CATEGORIES:
            _, was_created = Category.objects.get_or_create(name=name)
            if was_created:
                created += 1
        total = Category.objects.filter(name__in=PERSONNEL_CATEGORIES).count()
        self.stdout.write(self.style.SUCCESS(
            f"Catégories personnel : {total} présentes ({created} créée(s))."
        ))
        for cat in Category.objects.filter(name__in=PERSONNEL_CATEGORIES).order_by("name"):
            self.stdout.write(f"  - {cat.name}")
