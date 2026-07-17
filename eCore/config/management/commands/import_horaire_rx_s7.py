"""
Import de l'horaire officiel — Master 1 RX (Réseaux), Semestre 7 (2025-2026).
Source : HORAIRE DES UE MASTER SEMESTRE 7 - RS.pdf

Usage:
  python manage.py import_horaire_rx_s7
  python manage.py import_horaire_rx_s7 --clear
"""
from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, ElementConstitutif, Filiere, Local, Semestre
from prestation.models import Horaire, HoraireLigne

# Créneaux lus colonne par colonne (Lundi → Samedi) depuis le PDF officiel.
# Format : jour, début, fin, code EC, enseignant, n° local
RX_S7_HORAIRE = [
    (HoraireLigne.JOUR_LUNDI, time(16, 0), time(18, 0), "REE2171-EC1", "LONGO ARMAND", "12"),
    (HoraireLigne.JOUR_LUNDI, time(18, 0), time(20, 0), "REE2171-EC2", "MATONDO NSUMBU", "12"),
    (HoraireLigne.JOUR_MARDI, time(16, 0), time(18, 0), "REE2171-EC3", "KANYINDA NZUZI", "12"),
    (HoraireLigne.JOUR_MARDI, time(18, 0), time(20, 0), "MRI2173", "KAZADI TSHAMALA", "12"),
    (HoraireLigne.JOUR_MERCREDI, time(16, 0), time(18, 0), "GFC2172", "BABAKA TUNGULU", "16"),
    (HoraireLigne.JOUR_MERCREDI, time(18, 0), time(20, 0), "RSI2175", "MBIYA MPOYI", "16"),
    (HoraireLigne.JOUR_JEUDI, time(16, 0), time(18, 0), "AWS2172", "TAKOYI LUNDULA", "12"),
    (HoraireLigne.JOUR_JEUDI, time(18, 0), time(20, 0), "MRI2173", "KAZADI TSHAMALA", "12"),
    (HoraireLigne.JOUR_VENDREDI, time(16, 0), time(18, 0), "LAN2174-EC1", "BADIBANGA MICHEL", "16"),
    (HoraireLigne.JOUR_VENDREDI, time(18, 0), time(20, 0), "LAN2174-EC2", "MUTUAMBUKA", "12"),
    (HoraireLigne.JOUR_SAMEDI, time(10, 0), time(12, 0), "REE2171-EC1", "LONGO ARMAND", "11"),
]

EC_CODE_ALIASES = {
    "LAN2176": "LAN2174-EC1",
    "ECUE 2": "LAN2174-EC2",
    "ECUE2": "LAN2174-EC2",
    "RSI2178": "RSI2175",
    "ADMINISTRATION WINDOWS SERVER": "AWS2172",
}


class Command(BaseCommand):
    help = "Importe l'horaire Master 1 RX — Semestre 7 (2025-2026)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime les lignes existantes de cet horaire avant import",
        )

    def handle(self, *args, **options):
        annee = AnneeAcademique.get_active()
        if not annee:
            self.stderr.write(self.style.ERROR("Aucune année académique active."))
            return

        filiere = Filiere.objects.filter(code="RX").first()
        if not filiere:
            self.stderr.write(self.style.ERROR("Filière RX introuvable."))
            return

        semestre = Semestre.objects.filter(code="S7").first()
        if not semestre:
            self.stderr.write(self.style.ERROR("Semestre S7 introuvable."))
            return

        classe = Classe.objects.filter(
            promotion__filiere=filiere,
            code="A",
            active=True,
        ).first()
        if not classe:
            self.stderr.write(self.style.ERROR("Classe A RX introuvable."))
            return

        with transaction.atomic():
            horaire, created = Horaire.objects.update_or_create(
                annee_academique=annee,
                classe=classe,
                semestre=semestre,
                defaults={
                    "titre": "Horaire des unités d'enseignement",
                    "observation": "Fait à Kinshasa, le 11/03/2026 — Master 1 RX",
                    "active": True,
                },
            )

            if options["clear"] or created:
                horaire.lignes.all().delete()

            created_lines = 0
            for ordre, slot in enumerate(RX_S7_HORAIRE, start=1):
                jour, heure_debut, heure_fin, code, enseignant, local_num = slot
                local = self._get_or_create_local(local_num)
                ec = self._resolve_ec(code, filiere, semestre)
                if not ec:
                    self.stderr.write(self.style.WARNING(f"EC introuvable pour le code {code!r} — ligne ignorée."))
                    continue

                HoraireLigne.objects.create(
                    horaire=horaire,
                    jour=jour,
                    heure_debut=heure_debut,
                    heure_fin=heure_fin,
                    ue_code=ec.code,
                    element_constitutif=ec,
                    local=local,
                    notes=f"Enseignant: {enseignant}",
                    ordre=ordre,
                )
                created_lines += 1

        self.stdout.write(self.style.SUCCESS(
            f"Horaire RX S7 importé : {created_lines} créneaux "
            f"({classe.promotion.code}-{classe.code}, {annee.code})."
        ))
        self.stdout.write(f"  Voir : Prestations > Horaires (id={horaire.pk})")

    def _get_or_create_local(self, numero):
        code = f"L{numero}" if not str(numero).startswith("L") else str(numero)
        local, _ = Local.objects.get_or_create(
            code=code,
            defaults={"nom": f"Local {numero}", "capacite": 40, "active": True},
        )
        return local

    def _resolve_ec(self, code, filiere, semestre):
        key = code.strip().upper()
        normalized = EC_CODE_ALIASES.get(key, key)
        qs = ElementConstitutif.objects.filter(
            ue__filiere=filiere,
            ue__semestre=semestre,
        )
        ec = qs.filter(code__iexact=normalized).first()
        if ec:
            return ec
        return qs.filter(code__iexact=code.strip()).first()
