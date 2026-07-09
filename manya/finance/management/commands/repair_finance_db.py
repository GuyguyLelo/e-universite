from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Recrée finance_confirmationpaiement si la migration est désynchronisée.'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.finance_confirmationpaiement')")
            table_exists = cursor.fetchone()[0] is not None

        if table_exists:
            self.stdout.write(self.style.SUCCESS('La table finance_confirmationpaiement existe déjà.'))
            return

        self.stdout.write(self.style.WARNING('Table absente — réapplication de la migration 0003…'))
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = %s AND name = %s",
                ['finance', '0003_confirmationpaiement'],
            )

        call_command('migrate', 'finance', '0003_confirmationpaiement', verbosity=1)
        self.stdout.write(self.style.SUCCESS('Migration finance.0003 réappliquée.'))
