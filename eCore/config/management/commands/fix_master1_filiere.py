"""
Corrige le rattachement filière des promotions Master 1 et resynchronise les inscriptions
à partir des listes officielles (par nom, pas seulement par préfixe M1CSI/M1RX).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, Filiere, Promotion
from config.management.commands.import_etudiants_master1 import (
    CSI_ETUDIANTS,
    RX_ETUDIANTS,
    _nom_prenom,
)
from students.matricule import (
    apply_matricule_assignments,
    build_matricule_assignments,
    matricule_year_default,
)
from students.models import Inscription, Student


def _find_student(row):
    full_nom, prenom_field = _nom_prenom(*row[:3])
    return Student.objects.filter(nom=full_nom, prenom=prenom_field).first()


class Command(BaseCommand):
    help = (
        "Rattache PMC→CSI, PMR→RX et réaffecte chaque étudiant Master 1 "
        "selon les listes officielles CSI / RX."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--swap-classes",
            action="store_true",
            help="Inverse l'affectation des listes CSI/RX vers PMC/PMR (correction d'un import inversé).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        filiere_csi = Filiere.objects.filter(code="CSI").first()
        filiere_rx = Filiere.objects.filter(code="RX").first()
        pmc = Promotion.objects.filter(code="PMC").first()
        pmr = Promotion.objects.filter(code="PMR").first()

        if not all([filiere_csi, filiere_rx, pmc, pmr]):
            self.stderr.write(self.style.ERROR("Filières CSI/RX ou promotions PMC/PMR introuvables."))
            return

        promo_fixes = 0
        if pmc.filiere_id != filiere_csi.id:
            pmc.filiere = filiere_csi
            pmc.save(update_fields=["filiere_id"])
            promo_fixes += 1
            self.stdout.write("PMC rattachée à la filière CSI (Conception).")

        if pmr.filiere_id != filiere_rx.id:
            pmr.filiere = filiere_rx
            pmr.save(update_fields=["filiere_id"])
            promo_fixes += 1
            self.stdout.write("PMR rattachée à la filière RX (Réseaux).")

        classe_csi = Classe.objects.filter(promotion=pmc, code="A").first()
        classe_rx = Classe.objects.filter(promotion=pmr, code="A").first()
        if not classe_csi or not classe_rx:
            self.stderr.write(self.style.ERROR("Classes A introuvables pour PMC ou PMR."))
            return

        annee = AnneeAcademique.get_active()
        if not annee:
            self.stderr.write(self.style.ERROR("Aucune année académique active."))
            return

        swap = options["swap_classes"]
        if swap:
            csi_target = classe_rx
            rx_target = classe_csi
            self.stdout.write("Mode inversion : liste CSI -> PMR, liste RX -> PMC.")
        else:
            csi_target = classe_csi
            rx_target = classe_rx

        targets = []
        for row in CSI_ETUDIANTS:
            targets.append((row, csi_target))
        for row in RX_ETUDIANTS:
            targets.append((row, rx_target))

        students = []
        missing = []
        for row, classe in targets:
            student = _find_student(row)
            if not student:
                missing.append(_nom_prenom(*row[:3])[0])
                continue
            students.append((student, classe))

        if missing:
            self.stderr.write(
                self.style.WARNING(f"Étudiants introuvables ({len(missing)}): {', '.join(missing[:5])}…")
            )

        moved = 0
        for student, classe in students:
            ins = Inscription.objects.filter(
                etudiant=student,
                annee_academique=annee,
            ).first()
            if not ins:
                continue
            if ins.classe_id != classe.id:
                ins.classe = classe
                ins.save(update_fields=["classe_id"])
                moved += 1

        year = matricule_year_default(annee)
        assignments = build_matricule_assignments(annee, year=year)
        renumbered = apply_matricule_assignments(assignments, update_email=True)

        csi_n = Student.objects.filter(
            inscriptions__annee_academique=annee,
            inscriptions__classe__promotion__filiere=filiere_csi,
        ).distinct().count()
        rx_n = Student.objects.filter(
            inscriptions__annee_academique=annee,
            inscriptions__classe__promotion__filiere=filiere_rx,
        ).distinct().count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé — promotions corrigées: {promo_fixes}, "
                f"numéros réalignés: {renumbered}, inscriptions déplacées: {moved}. "
                f"Conception (CSI): {csi_n}, Réseaux (RX): {rx_n}."
            )
        )
