"""
Import Master 1 CSI 2025-2026 — liste officielle (59 apprenants).
Réutilise les fiches étudiants déjà inscrites en Pre-Master pour éviter les doublons.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, Filiere, Promotion
from students.matricule import (
    apply_matricule_assignments,
    build_matricule_assignments_from_lists,
    matricule_year_default,
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


# Liste officielle Master 1 CSI 2025-2026 (NOM, POSTNOM, PRENOM, SEXE, TELEPHONE)
CSI_M1_2526_ETUDIANTS = [
    ("ABDALA", "NOTIA", "RUTH", "F", "857630368"),
    ("ABIZI", "EDJOKOLA", "MIRADI", "F", "893833971"),
    ("AMISI", "ASSANGO", "LIONEL", "M", "890237987"),
    ("BAKAJI", "KANYANYA", "MONICA", "F", "844207962"),
    ("BELE", "NGUMA", "DANIEL", "M", "978923254"),
    ("BOLOLA", "MALOYI", "RALPH", "M", "820623339"),
    ("BONGOTA", "EMEKA", "HERITIER", "M", "810478430"),
    ("BUZITU", "KEITA", "SERDY", "M", "830778696"),
    ("DIKIZEYIKO", "MAKESE", "BLESSING", "F", "847194155"),
    ("ESTOL", "MOKIMO", "GRACE", "F", "973400102"),
    ("FAHIDA", "DAKUNDU", "RAGINA", "F", "829844618"),
    ("GINENGA", "SELE", "JERMIE", "M", "990719380"),
    ("ISEMOLI", "ELONGO", "JAELLE", "F", "972713006"),
    ("KADIMA", "NGOYI", "PANIEL", "M", "975191705"),
    ("KAKESA", "MPONO", "GOEL", "M", "845024983"),
    ("KALONDA", "WUTSHU", "GEORGES", "M", "823979834"),
    ("KALONJI", "MUKUNA", "FRANCK", "M", "810007093"),
    ("KAMWANYA", "MULUMBA", "BENEDICTE", "F", "833087563"),
    ("KANDE", "BABADI", "NATHAN", "M", "824202218"),
    ("KATSHAY", "MPENGO", "EXAUCEE", "F", "814912405"),
    ("KAWELE", "MBEMBI", "KEVIN", "M", "825866941"),
    ("KAZADI", "KONGOLO", "HERVE", "M", "846846983"),
    ("KHUBA", "MAVINGA", "ELYON", "M", "973812680"),
    ("KIANGEBENI", "MATONDO", "HERMINE", "F", "980657709"),
    ("KOMBO", "IWEWE", "MERVEILLE", "F", "993563092"),
    ("LOMBOTO", "BOLONGO", "HENOC", "M", "978481920"),
    ("LUEMBA", "MBEDIKA", "JORDANE", "M", "815829718"),
    ("LUFIY", "MAFUTA", "MERCE", "M", "822685864"),
    ("MAKUNGU", "MAYAKAMBUA", "DIEUDONNE", "M", "848435278"),
    ("MAMBA", "BADIBANGA", "DEBORAH", "F", "981576339"),
    ("MANSIANGI", "MBALA", "GRACIA", "F", "899907136"),
    ("MANZANZA", "MUSANGU", "SOLANGE", "F", "825049589"),
    ("MASAMUNA", "KYUNDU", "DJEBIE", "F", "850675669"),
    ("METHA", "MABITA", "BERNATHAN", "M", "977512448"),
    ("MPUTU", "IFOSO", "MOISE", "M", "897936027"),
    ("MUHETO", "MADISEKULA", "GRADIE", "M", "816101110"),
    ("MUJINGA", "KAZOVU", "PAPY", "M", "815081894"),
    ("MULUMBA", "ILUNGA", "JEREMIE", "M", "898245698"),
    ("MUSASA", "LOTIKA", "NATHAN", "M", "897107830"),
    ("NDOKO", "MAVULA", "JONAS", "M", "821154999"),
    ("NGALULA", "ILUNGA", "MARTHE", "F", "973524282"),
    ("NGONGO", "SELE", "CHARLENE", "F", "816880477"),
    ("NKWANSAMBU", "MAMBOTE", "AESTHER", "F", "990617921"),
    ("NTUMBA", "NSAMBAYI", "MARIA", "F", "897357036"),
    ("NTUMBA", "LUSHIKU", "MICHEE", "M", "813920883"),
    ("NUNGA", "MIDI", "GRACE", "M", "822450056"),
    ("NZUMI", "KAM", "PERRIN", "M", "812424210"),
    ("OMALOWETE", "MANYA", "ALPHONSE", "M", "859178041"),
    ("OTEMANYANGA", "TAKENGE", "RACHEL", "F", "813827260"),
    ("PAY", "KAPWANGA", "COVO", "M", "896346362"),
    ("PINDU", "PINDI", "DJO", "M", "812645617"),
    ("RAMAZANI", "ISSA", "NAOMI", "F", "906662413"),
    ("SABU", "MBAYI", "EVELYNE", "F", "812136455"),
    ("SHARADI", "NEHEMA", "LINDA", "M", ""),
    ("SHUKURU", "KUBUYA", "TILAMOVIC", "M", "894181981"),
    ("TSHIBANGU", "MULAJA", "MERVEILLE", "F", "821083162"),
    ("WAKIMESA", "KIMPILAMPILA", "GUY", "M", "892204971"),
    ("WANGE", "MBO", "EVODIE", "F", "840853863"),
    ("WETSHU", "OKONDA", "BIENVENU", "M", "816540445"),
]


class Command(BaseCommand):
    help = "Importe la liste Master 1 CSI 2025-2026 en réutilisant les fiches Pre-Master existantes."

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
        filiere_csi = Filiere.objects.filter(code="CSI").first()
        pmc = Promotion.objects.filter(code="PMC").first()
        classe_csi = Classe.objects.filter(promotion=pmc, code="A").first() if pmc else None

        if not filiere_csi or not pmc or not classe_csi:
            self.stderr.write(self.style.ERROR("Filière CSI, promotion PMC ou classe A introuvable."))
            return
        if pmc.filiere_id != filiere_csi.id:
            pmc.filiere = filiere_csi
            pmc.save(update_fields=["filiere_id"])

        created_students = 0
        reused_students = 0
        reused_premaster = 0
        created_inscriptions = 0
        ins_counter = Inscription.objects.count() + 1
        temp_counter = Student.objects.count()
        imported_students = []

        for nom, postnom, prenom, sexe, telephone in CSI_M1_2526_ETUDIANTS:
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
                if sexe and etudiant.sexe != sexe:
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
                    sexe=sexe or "M",
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
                    "classe": classe_csi,
                    "numero_inscription": numero_ins,
                    "statut": "inscrit",
                    "frais_inscription": Decimal("0"),
                    "frais_payes": Decimal("0"),
                },
            )
            if not ins_created:
                changed = []
                if inscription.classe_id != classe_csi.id:
                    inscription.classe = classe_csi
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

        csi_rows = [row[:4] for row in CSI_M1_2526_ETUDIANTS]
        year_fin = matricule_year_default(annee)

        def _find_for_matricule(row):
            nom, postnom, prenom, _sexe = row
            student, _ = _find_existing_student(nom, postnom, prenom, annee_premaster)
            return student

        matricule_assignments = build_matricule_assignments_from_lists(
            annee, csi_rows, [], _find_for_matricule
        )

        matricules = apply_matricule_assignments(matricule_assignments, update_email=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport Master 1 CSI {annee.code} — {len(CSI_M1_2526_ETUDIANTS)} apprenant(s)\n"
                f"  Fiches réutilisées : {reused_students} (dont pre-master : {reused_premaster})\n"
                f"  Nouveaux étudiants : {created_students}\n"
                f"  Inscriptions créées : {created_inscriptions}\n"
                f"  Matricules CSI attribués : {matricules} (format {year_fin}####)\n"
                f"  Classe : {classe_csi} ({pmc.code})"
            )
        )
