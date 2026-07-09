"""
Import Master 1 RX 2025-2026 — liste officielle (22 apprenants).
Réutilise les fiches étudiants déjà inscrites en Pre-Master pour éviter les doublons.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, Filiere, Promotion
from students.matricule import (
    apply_matricule_assignments,
    build_master_rx_matricule_assignments,
    build_matricule_assignments_from_lists,
)
from students.models import DossierEtudiant, Inscription, Student


def _nom_prenom(nom, postnom, prenom):
    full_nom = f"{nom} {postnom}".strip() if postnom else nom
    if prenom:
        return full_nom, prenom
    if postnom and not prenom:
        return nom, postnom
    return full_nom, "—"


def _find_existing_student(nom, postnom, prenom, annee_premaster):
    """Recherche par nom/prénom exacts, puis parmi les inscrits Pre-Master."""
    nom_field, prenom_field = _nom_prenom(nom, postnom, prenom)
    student = Student.objects.filter(nom__iexact=nom_field, prenom__iexact=prenom_field).first()
    if student:
        return student, "exact"

    if not annee_premaster:
        return None, None

    prenom_key = prenom_field.strip().upper()
    nom_key = nom.strip().upper()

    for student in (
        Student.objects.filter(inscriptions__annee_academique=annee_premaster)
        .distinct()
        .order_by("pk")
    ):
        s_nom = (student.nom or "").upper()
        s_pre = (student.prenom or "").upper()
        if s_pre == prenom_key and (s_nom == nom_field.upper() or s_nom.startswith(nom_key + " ")):
            return student, "pre-master"
        if s_pre == prenom_key and nom_key in s_nom.split():
            return student, "pre-master"

    return None, None


# Liste officielle Master 1 RX 2025-2026 (NOM, POSTNOM, PRENOM, SEXE, TELEPHONE)
RX_M1_2526_ETUDIANTS = [
    ("BADRIYO", "MARINDO", "KING", "M", "981808556"),
    ("BAMBUSE", "ENGEMBELE", "ZACHARIE", "M", "822000064"),
    ("BONYAMBALA", "YAKUSU", "SAEL", "M", "838825978"),
    ("FETA", "NKASA", "FADI", "F", "826249964"),
    ("IYAMA", "LAKUNG", "SANTA", "F", "997933016"),
    ("KAMUNYI", "KAKONDE", "NARCISSE", "M", "829552228"),
    ("KANKOLONGO", "KABENGELE", "CAROL", "F", "843213331"),
    ("KAPIA", "MUTOMBO", "DAVINA", "F", "990635149"),
    ("MABONDO", "NSATUKANDA", "BENEDICTE", "F", "971972586"),
    ("MAKUZULU", "NZAZI", "JUNIOR", "M", "812668309"),
    ("MALONDA", "DODY", "JEREMIE", "M", "850828229"),
    ("MASUDI", "MIGEYA", "JACQUES", "M", "816262398"),
    ("MBAYO", "MUKALAMUSI", "AMEDE", "M", "821707309"),
    ("META", "KADIAMBA", "GLOIRE", "M", "905076191"),
    ("MWANZA", "MBUYI", "BENEDICTE", "F", "984169960"),
    ("NSIMIRE", "CHIRUZA", "VENANCYA", "F", "822689322"),
    ("NSINGI", "NDOMBASI", "JEREMIE", "M", "825060071"),
    ("NSUALA", "BAKELUBA", "GRACE", "M", "824062626"),
    ("NYATH", "IYOLO", "WALTER", "M", "812700875"),
    ("PALAKI", "BOLAWELO", "PLATINI", "M", "822092000"),
    ("SETH", "MASUDI", "USHINDI", "M", "818808469"),
    ("VIKA", "KAJINGA", "MIRIAM", "F", "818453789"),
]


class Command(BaseCommand):
    help = "Importe la liste Master 1 RX 2025-2026 en réutilisant les fiches Pre-Master existantes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--annee",
            default="2025-2026",
            help="Code année académique (défaut : 2025-2026).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        annee = AnneeAcademique.objects.filter(code=options["annee"]).first()
        if not annee:
            self.stderr.write(self.style.ERROR(f"Année {options['annee']} introuvable."))
            return

        annee_premaster = AnneeAcademique.objects.filter(code="2024-2025").first()
        filiere_rx = Filiere.objects.filter(code="RX").first()
        pmr = Promotion.objects.filter(code="PMR").first()
        classe_rx = Classe.objects.filter(promotion=pmr, code="A").first() if pmr else None

        if not filiere_rx or not pmr or not classe_rx:
            self.stderr.write(self.style.ERROR("Filière RX, promotion PMR ou classe A introuvable."))
            return
        if pmr.filiere_id != filiere_rx.id:
            pmr.filiere = filiere_rx
            pmr.save(update_fields=["filiere_id"])

        created_students = 0
        reused_students = 0
        reused_premaster = 0
        created_inscriptions = 0
        ins_counter = Inscription.objects.count() + 1
        temp_counter = Student.objects.count()
        imported_students = []

        for nom, postnom, prenom, sexe, telephone in RX_M1_2526_ETUDIANTS:
            nom_field, prenom_field = _nom_prenom(nom, postnom, prenom)
            etudiant, match_kind = _find_existing_student(nom, postnom, prenom, annee_premaster)

            if etudiant:
                reused_students += 1
                if match_kind == "pre-master":
                    reused_premaster += 1
                    self.stdout.write(
                        f"  Réutilisé (pre-master) : {etudiant.numero_etudiant} — {etudiant.identite_cotation}"
                    )
                update_fields = []
                if telephone and etudiant.telephone != telephone:
                    etudiant.telephone = telephone
                    update_fields.append("telephone")
                if etudiant.sexe != sexe:
                    etudiant.sexe = sexe
                    update_fields.append("sexe")
                if update_fields:
                    etudiant.save(update_fields=update_fields)
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
                    telephone=telephone or None,
                    nationalite="Congolaise",
                    statut="actif",
                )
                created_students += 1
                self.stdout.write(f"  Nouveau : {etudiant.identite_cotation}")

            numero_ins = f"INS{annee.annee_debut}{ins_counter:04d}"
            ins_counter += 1
            inscription, ins_created = Inscription.objects.get_or_create(
                etudiant=etudiant,
                annee_academique=annee,
                defaults={
                    "classe": classe_rx,
                    "numero_inscription": numero_ins,
                    "statut": "inscrit",
                    "frais_inscription": Decimal("0"),
                    "frais_payes": Decimal("0"),
                },
            )
            if not ins_created:
                changed = []
                if inscription.classe_id != classe_rx.id:
                    inscription.classe = classe_rx
                    changed.append("classe_id")
                if inscription.statut != "inscrit":
                    inscription.statut = "inscrit"
                    changed.append("statut")
                if changed:
                    inscription.save(update_fields=changed)
            else:
                created_inscriptions += 1
                DossierEtudiant.objects.get_or_create(
                    inscription=inscription,
                    defaults={"statut": "en_cours"},
                )

            imported_students.append(etudiant)

        rx_rows = [row[:4] for row in RX_M1_2526_ETUDIANTS]

        def _find_for_matricule(row):
            nom, postnom, prenom, _sexe = row
            student, _ = _find_existing_student(nom, postnom, prenom, annee_premaster)
            return student

        matricule_assignments = build_matricule_assignments_from_lists(
            annee, [], rx_rows, _find_for_matricule
        )
        if len(matricule_assignments) < len(RX_M1_2526_ETUDIANTS):
            matricule_assignments = build_master_rx_matricule_assignments(
                annee, students=imported_students
            )

        matricules = apply_matricule_assignments(matricule_assignments, update_email=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport Master 1 RX {annee.code} — {len(RX_M1_2526_ETUDIANTS)} apprenant(s)\n"
                f"  Fiches réutilisées : {reused_students} (dont pre-master : {reused_premaster})\n"
                f"  Nouveaux étudiants : {created_students}\n"
                f"  Inscriptions créées : {created_inscriptions}\n"
                f"  Matricules RX attribués : {matricules} (format {annee.annee_debut}###)\n"
                f"  Classe : {classe_rx} ({pmr.code})"
            )
        )
