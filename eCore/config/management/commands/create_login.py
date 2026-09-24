"""
Crée ou réinitialise le compte administrateur e-Université.

Usage:
  python manage.py create_login
  python manage.py create_login --username admin --password MonMotDePasse
  python manage.py create_login --reset
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée ou réinitialise le compte administrateur de connexion e-Université."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="admin",
            help="Identifiant de connexion (défaut : admin)",
        )
        parser.add_argument(
            "--password",
            default="admin123",
            help="Mot de passe (défaut : admin123)",
        )
        parser.add_argument(
            "--email",
            default="admin@localhost",
            help="Adresse e-mail du compte",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Réinitialise le mot de passe si le compte existe déjà",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        email = options["email"].strip()
        reset = options["reset"]

        if not username:
            self.stderr.write(self.style.ERROR("Le nom d'utilisateur ne peut pas être vide."))
            return

        if not password:
            self.stderr.write(self.style.ERROR("Le mot de passe ne peut pas être vide."))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": "Admin",
                "last_name": "e-Université",
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Compte créé : {username}"))
        elif reset:
            user.email = email or user.email
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Compte réinitialisé : {username}"))
        else:
            self.stdout.write(self.style.WARNING(
                f"Le compte « {username} » existe déjà. Utilisez --reset pour changer le mot de passe."
            ))
            return

        self.stdout.write("")
        self.stdout.write("Connexion e-Université :")
        self.stdout.write(f"  URL      : /accounts/login/")
        self.stdout.write(f"  Username : {username}")
        self.stdout.write(f"  Password : {password}")
        self.stdout.write(self.style.WARNING("Changez le mot de passe après la première connexion."))
