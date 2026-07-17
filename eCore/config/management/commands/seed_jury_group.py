"""
Crée le groupe Django « Jury » avec les permissions de consultation des délibérations.

Usage:
  python manage.py seed_jury_group
  python manage.py seed_jury_group --assign admin prof1 prof2
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from deliberations.access import JURY_GROUP_NAME, JURY_GROUP_PERMISSION_CODENAMES

User = get_user_model()


class Command(BaseCommand):
    help = "Crée le groupe Jury et assigne les permissions de consultation des délibérations."

    def add_arguments(self, parser):
        parser.add_argument(
            '--assign',
            nargs='*',
            metavar='USERNAME',
            help="Ajoute un ou plusieurs utilisateurs au groupe Jury",
        )

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name=JURY_GROUP_NAME)
        perms = Permission.objects.filter(
            content_type__app_label='deliberations',
            codename__in=JURY_GROUP_PERMISSION_CODENAMES,
        )
        found = set(perms.values_list('codename', flat=True))
        missing = set(JURY_GROUP_PERMISSION_CODENAMES) - found
        if missing:
            self.stderr.write(self.style.ERROR(
                f"Permissions introuvables : {', '.join(sorted(missing))}"
            ))
            return

        group.permissions.set(perms)
        action = 'créé' if created else 'mis à jour'
        self.stdout.write(self.style.SUCCESS(
            f"Groupe « {JURY_GROUP_NAME} » {action} — {perms.count()} permission(s)."
        ))
        for perm in perms.order_by('codename'):
            self.stdout.write(f"  - deliberations.{perm.codename}")

        usernames = options.get('assign') or []
        for username in usernames:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stderr.write(self.style.WARNING(f"Utilisateur introuvable : {username}"))
                continue
            group.user_set.add(user)
            self.stdout.write(self.style.SUCCESS(f"  → {username} ajouté au groupe Jury"))
