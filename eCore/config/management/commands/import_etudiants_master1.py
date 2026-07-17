"""
Import des étudiants Master 1 — CSI et Réseaux (liste officielle).
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, Filiere, Promotion
from students.matricule import apply_matricule_assignments, build_matricule_assignments
from students.models import DossierEtudiant, Inscription, Student


def _nom_prenom(nom, postnom, prenom):
    """Nom complet (nom + postnom) et prénom d'usage."""
    full_nom = f"{nom} {postnom}".strip() if postnom else nom
    if prenom:
        return full_nom, prenom
    if postnom and not prenom:
        return nom, postnom
    return full_nom, "—"


CSI_ETUDIANTS = [
    ("ABDALA", "NOTIA", "", "F"),
    ("ABIZI", "EDJOKOLA", "MIRADI", "M"),
    ("BADRIYO", "MARINDO", "KING", "M"),
    ("DAMBUSE", "ENGEMBELE", "ZACHARIE", "M"),
    ("DIZITU", "KEITA", "", "M"),
    ("FETA", "NKASA", "FADI", "F"),
    ("FWAMA", "MUKANSONG", "", "M"),
    ("IYAMA", "LUKUNG", "SANTA", "F"),
    ("KALONDA", "WETSHU", "GEORGES", "M"),
    ("KANKOLONGO", "KABENGELE", "CAROL", "F"),
    ("KAZADI", "KONCOLO", "HERVE", "M"),
    ("MABONDO", "NSATUKANDA", "BENEDICTE", "F"),
    ("MAKUZULU", "NZAZI", "JUNIOR", "M"),
    ("MALONDA", "DODY", "JEREMIE-SAGACE", "M"),
    ("MASUDI", "MIGEYA", "JACQUES", "M"),
    ("MBAYO", "MUKALAMUSI", "AMEDE", "M"),
    ("META", "KADIAMBA", "METE", "M"),
    ("MWAMBA", "NZAMBI", "MWIN", "M"),
    ("MWANZA", "MBUYI", "BENEDICTE", "F"),
    ("NSIMIRE", "CHIRUZA", "VENANCYA", "F"),
    ("NSINGI", "NDOMBASI", "", "M"),
    ("NSUALA", "BAKELUBA", "GRACE", "M"),
    ("OMALOWETE", "MANYA", "", "M"),
    ("PALAKI", "BOLAWELO", "PLATINI", "M"),
    ("SETH", "MASUDI", "USHINDI", "M"),
    ("VIKA", "KAJINGA", "MIRIAM", "F"),
]

RX_ETUDIANTS = [
    ("AMISI", "ASSANGO", "LIONEL", "M"),
    ("BELE", "NGUMA", "", "M"),
    ("BOLOLA", "MALOYI", "", "M"),
    ("BONGOTA", "EMEKA", "HERITIER", "M"),
    ("BONYAMBALA", "YAKUSU", "SAEL", "M"),
    ("DIKIZEYIKO", "MAKIESE", "", "M"),
    ("ESTOL", "MOKIMO", "GRACE", "F"),
    ("GINENGA", "MWAMBA", "", "M"),
    ("ISEMOLI", "ELONGO", "", "F"),
    ("KADIMA", "NGOYI", "DANIEL", "M"),
    ("KAKESA", "MPONO", "GOEL", "M"),
    ("KALONJI", "MUKUNA", "FRANCK", "M"),
    ("KAMUNYI", "KANKONDE", "NARCISSE", "M"),
    ("KAMWANYA", "MULUMBA", "", "M"),
    ("KANDE", "BABADI", "", "M"),
    ("KATSHAY", "MPENGO", "EXAUCEE", "F"),
    ("KAWELE", "MBEMBI", "KEVIN", "M"),
    ("KHUBA", "MAVINGA", "ELYON", "M"),
    ("KIANGEBENI", "MATONDO", "", "M"),
    ("KOMBO", "IWEWE", "MERVEILLE", "F"),
    ("LOMBOTO", "BOLONGO", "HENOC", "M"),
    ("LUEMBA", "MBEDIKA", "JORDANE", "M"),
    ("LUHY", "MAFUTA", "MERCE", "M"),
    ("MAKUNGU", "MAYAKAMBUA", "", "M"),
    ("MAMBA", "BADIBANGA", "", "F"),
    ("MANSIANGI", "MBALA", "GRACIA", "F"),
    ("MASAMUNA", "KYUNGU", "DJEBIE", "F"),
    ("METHA", "MABITA", "BERNATHAN", "F"),
    ("MPUTU", "IFOSO", "", "M"),
    ("MUHETO", "MADISEKULA", "GRADIE", "F"),
    ("MUJINGA", "KAZOVU", "PAPY", "M"),
    ("MUSASA", "LOTIKA", "", "M"),
    ("NDOKO", "MAVULA", "", "M"),
    ("NGALULA", "ILUNGA", "", "F"),
    ("NCONGO", "SELE", "CHARLENE", "F"),
    ("NKWANSAMBU", "MAMBOTE", "", "F"),
    ("NTUMBA", "LUSHIKU", "", "M"),
    ("NYATH", "IYOLO", "WALTER", "M"),
    ("NZUMBI", "KAMI", "PERRIN", "M"),
    ("OTEMANYANGA", "TAKENGE", "RACHEL", "F"),
    ("PAY", "KAPWANGA", "COVO", "M"),
    ("PEMBA", "LONGO", "", "F"),
    ("PINDU", "PINDI", "DIO", "M"),
    ("RAMAZANI", "ISSA", "", "M"),
    ("SABU", "MBAYI", "EVELYNE", "F"),
    ("SHARADI", "REHEMA", "LINDA", "F"),
    ("SHUKURU", "KUBUYA", "TILAMOVIC", "M"),
    ("TSHIBANGU", "MULUA", "", "M"),
    ("WAKIMESA", "KIMPALAMPALA", "GUY", "M"),
    ("WANGE", "MBO", "EVODIE", "F"),
]


class Command(BaseCommand):
    help = "Importe les étudiants Master 1 CSI et Réseaux."

    @transaction.atomic
    def handle(self, *args, **options):
        annee = AnneeAcademique.get_active()
        if not annee:
            self.stderr.write(self.style.ERROR("Aucune année académique active."))
            return

        filiere_csi = Filiere.objects.filter(code="CSI").first()
        filiere_rx = Filiere.objects.filter(code="RX").first()
        if not filiere_csi or not filiere_rx:
            self.stderr.write(self.style.ERROR("Filières CSI ou RX introuvables."))
            return

        pmc = Promotion.objects.filter(code="PMC").first()
        pmr = Promotion.objects.filter(code="PMR").first()
        if not pmc or not pmr:
            self.stderr.write(self.style.ERROR("Promotions PMC ou PMR introuvables."))
            return

        if pmc.filiere_id != filiere_csi.id:
            pmc.filiere = filiere_csi
            pmc.save(update_fields=["filiere_id"])
        if pmr.filiere_id != filiere_rx.id:
            pmr.filiere = filiere_rx
            pmr.save(update_fields=["filiere_id"])

        classe_csi = Classe.objects.filter(promotion=pmc, code="A").first()
        classe_rx = Classe.objects.filter(promotion=pmr, code="A").first()
        if not classe_csi or not classe_rx:
            self.stderr.write(self.style.ERROR("Classes A introuvables pour CSI ou RX."))
            return

        promo_csi = pmc
        promo_rx = pmr

        created_students = 0
        created_inscriptions = 0
        ins_counter = Inscription.objects.count() + 1
        temp_counter = 0

        batches = [
            (CSI_ETUDIANTS, classe_csi, promo_csi),
            (RX_ETUDIANTS, classe_rx, promo_rx),
        ]

        for rows, classe, promotion in batches:
            for nom, postnom, prenom, sexe in rows:
                nom_field, prenom_field = _nom_prenom(nom, postnom, prenom)

                etudiant = Student.objects.filter(nom=nom_field, prenom=prenom_field).first()
                if etudiant:
                    created = False
                else:
                    temp_counter += 1
                    etudiant = Student.objects.create(
                        numero_etudiant=f"TMPIMP{temp_counter:05d}",
                        nom=nom_field,
                        prenom=prenom_field,
                        email=f"tmp{temp_counter:05d}@student.ecore.local",
                        date_naissance=date(2000, 1, 1),
                        lieu_naissance="Kinshasa",
                        sexe=sexe,
                        nationalite="Congolaise",
                        statut="actif",
                    )
                    created = True
                if created:
                    created_students += 1

                numero_ins = f"INS{annee.annee_debut}{ins_counter:04d}"
                ins_counter += 1
                inscription, ins_created = Inscription.objects.get_or_create(
                    etudiant=etudiant,
                    annee_academique=annee,
                    defaults={
                        "classe": classe,
                        "numero_inscription": numero_ins,
                        "statut": "inscrit",
                        "frais_inscription": Decimal("0"),
                        "frais_payes": Decimal("0"),
                    },
                )
                if not ins_created and inscription.classe_id != classe.id:
                    inscription.classe = classe
                    inscription.save(update_fields=["classe_id"])
                if ins_created:
                    created_inscriptions += 1
                    DossierEtudiant.objects.get_or_create(
                        inscription=inscription,
                        defaults={"statut": "en_cours"},
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {promotion.code} ({classe.code}) : {len(rows)} étudiant(s) traités"
                )
            )

        matricules = apply_matricule_assignments(
            build_matricule_assignments(annee),
            update_email=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport terminé — {created_students} étudiant(s) créé(s), "
                f"{created_inscriptions} inscription(s), "
                f"{matricules} matricule(s) attribué(s) (format année + n° d'ordre), "
                f"{Student.objects.count()} au total."
            )
        )
