"""
Import de l'horaire officiel — Master 1 CSI, Semestre 7 (2025-2026).
Source : HORAIRE DES UE MASTER SEMESTRE 7 - CSI.pdf

Usage:
  python manage.py import_horaire_csi_s7
  python manage.py import_horaire_csi_s7 --clear
"""
from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, ElementConstitutif, Filiere, Local, Semestre
from prestation.models import Horaire, HoraireLigne

# Créneaux lus colonne par colonne (Lundi → Samedi) depuis le PDF officiel.
CSI_S7_HORAIRE = [
  # jour, début, fin, code EC/UE, enseignant
    (HoraireLigne.JOUR_LUNDI, time(16, 0), time(18, 0), "ALG2171", "BOLA GANSHO"),
    (HoraireLigne.JOUR_LUNDI, time(18, 0), time(20, 0), "ING2173", "ADUSUMA YALANDA"),
    (HoraireLigne.JOUR_MARDI, time(16, 0), time(18, 0), "BDD2175", "TSHEFU ONATSHUNGU"),
    (HoraireLigne.JOUR_MARDI, time(18, 0), time(20, 0), "SYS2177", "KABALO KANT"),
    (HoraireLigne.JOUR_MERCREDI, time(16, 0), time(18, 0), "GFC2172", "BABAKA TUNGULU"),
    (HoraireLigne.JOUR_MERCREDI, time(18, 0), time(20, 0), "RSI2178", "MBIYA MPOYI"),
    (HoraireLigne.JOUR_JEUDI, time(16, 0), time(18, 0), "ING2173", "ADUSUMA YALANDA"),
    (HoraireLigne.JOUR_JEUDI, time(18, 0), time(20, 0), "ALG2171", "BOLA GANSHO"),
    (HoraireLigne.JOUR_VENDREDI, time(16, 0), time(18, 0), "LAN2176-EC1", "BADIBANGA MICHEL"),
    (HoraireLigne.JOUR_VENDREDI, time(18, 0), time(20, 0), "LAN2176-EC2", "TSHINGANI MANDEFU"),
    (HoraireLigne.JOUR_SAMEDI, time(10, 0), time(12, 0), "BDD2175", "TSHEFU ONATSHUNGU"),
]

EC_CODE_ALIASES = {
    "LAN2176": "LAN2176-EC1",
    "ECUE 2": "LAN2176-EC2",
    "ECUE2": "LAN2176-EC2",
}


class Command(BaseCommand):
    help = "Importe l'horaire Master 1 CSI — Semestre 7 (2025-2026)."

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

        filiere = Filiere.objects.filter(code="CSI").first()
        if not filiere:
            self.stderr.write(self.style.ERROR("Filière CSI introuvable."))
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
            self.stderr.write(self.style.ERROR("Classe A CSI introuvable."))
            return

        local = (
            Local.objects.filter(code="L16").first()
            or Local.objects.filter(code="16").first()
        )
        if not local:
            self.stderr.write(self.style.ERROR("Local 16 (L16) introuvable."))
            return

        with transaction.atomic():
            horaire, created = Horaire.objects.update_or_create(
                annee_academique=annee,
                classe=classe,
                semestre=semestre,
                defaults={
                    "titre": "Horaire des unités d'enseignement",
                    "observation": "Fait à Kinshasa, le 11/03/2026 — Master 1 CSI",
                    "active": True,
                },
            )

            if options["clear"] or created:
                horaire.lignes.all().delete()

            created_lines = 0
            for ordre, slot in enumerate(CSI_S7_HORAIRE, start=1):
                jour, heure_debut, heure_fin, code, enseignant = slot
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
            f"Horaire CSI S7 importé : {created_lines} créneaux "
            f"({classe.promotion.code}-{classe.code}, {annee.code})."
        ))
        self.stdout.write(f"  Voir : Prestations > Horaires (id={horaire.pk})")

    def _resolve_ec(self, code, filiere, semestre):
        normalized = EC_CODE_ALIASES.get(code.strip().upper(), code.strip().upper())
        qs = ElementConstitutif.objects.filter(
            ue__filiere=filiere,
            ue__semestre=semestre,
        )
        ec = qs.filter(code__iexact=normalized).first()
        if ec:
            return ec
        return qs.filter(code__iexact=code.strip()).first()
