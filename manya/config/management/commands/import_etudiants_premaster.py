"""
Import des apprenants Pre-Master (tronc commun) — liste officielle 2024-2025.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, Classe, Promotion
from students.matricule import apply_matricule_assignments, build_premaster_matricule_assignments
from students.models import DossierEtudiant, Inscription, Student


def _nom_prenom(nom, postnom, prenom):
    """Nom complet (nom + postnom) et prénom d'usage."""
    full_nom = f"{nom} {postnom}".strip() if postnom else nom
    if prenom:
        return full_nom, prenom
    if postnom and not prenom:
        return nom, postnom
    return full_nom, "—"


# Liste officielle Pre-Master 2024-2025 (NOM, POSTNOM, PRENOM, SEXE, TELEPHONE)
PREMASTER_ETUDIANTS = [
    ("ABDALA", "NOTIA", "RUTH", "F", "857630368"),
    ("AMISI", "ASSANGO", "LIONEL", "M", "890237987"),
    ("BADRIYO", "MARINDO", "KING", "M", "981808556"),
    ("BAKAJI", "KANYANYA", "MONICA", "F", "844207962"),
    ("BAMBUSE", "ENGEMBELE", "ZACHARIE", "M", "822000064"),
    ("BELE", "NGUMA", "DANIEL", "M", "978923254"),
    ("BOLOLA", "MALOYI", "RALPH", "M", "820623339"),
    ("BUZITU", "KEITA", "SERDY", "M", "830778696"),
    ("DIKIZEYIKO", "MAKESE", "BLESSING", "F", "847194155"),
    ("ESTOL", "MOKIMO", "GRACE", "F", "973400102"),
    ("FAHIDA", "DAKUNDU", "RAGINA", "F", "829844618"),
    ("GINENGA", "SELE", "JERMIE", "M", "990719380"),
    ("ISEMOLI", "ELONGO", "JAELLE", "F", "972713006"),
    ("KADIMA", "NGOYI", "PANIEL", "M", "975191705"),
    ("KALONJI", "MUKUNA", "FRANCK", "M", "810007093"),
    ("KAMWANYA", "MULUMBA", "BENEDICTE", "F", "833087563"),
    ("KANDE", "BABADI", "NATHAN", "M", "824202218"),
    ("KAPIA", "MUTOMBO", "DAVINA", "F", "990635149"),
    ("KAZADI", "KONGOLO", "HERVE", "M", "846846983"),
    ("KIANGEBENI", "MATONDO", "HERMINE", "F", "980657709"),
    ("MAKUZULU", "NZAZI", "JUNIOR", "M", "812668309"),
    ("MAMBA", "BADIBANGA", "DEBORAH", "F", "981576339"),
    ("MANZANZA", "MUSANGU", "SOLANGE", "F", "825049589"),
    ("MASAMUNA", "KYUNDU", "DJEBIE", "F", "850675669"),
    ("MASUDI", "MIGEYA", "JACQUES", "M", "816262398"),
    ("META", "KADIAMBA", "GLOIRE", "M", "905076191"),
    ("METHA", "MABITA", "BERNATHAN", "M", "977512448"),
    ("MPUTU", "IFOSO", "MOISE", "M", "897936027"),
    ("MUJINGA", "KAZOVU", "PAPY", "M", "815081894"),
    ("MUSASA", "LOTIKA", "NATHAN", "M", "897107830"),
    ("NGALULA", "ILUNGA", "MARTHE", "F", "973524282"),
    ("NGONGO", "SELE", "CHARLENE", "F", "816880477"),
    ("NTUMBA", "NSAMBAYI", "MARIA", "F", "897357036"),
    ("NTUMBA", "LUSHIKU", "MICHEE", "M", "813920883"),
    ("NUNGA", "MIDI", "GRACE", "M", "822450056"),
    ("OMALOWETE", "MANYA", "ALPHONSE", "M", "859178041"),
    ("OTEMANYANGA", "TAKENGE", "RACHEL", "M", "813827260"),
    ("PAY", "KAPWANGA", "COVO", "M", "896346362"),
    ("RAMAZANI", "ISSA", "NAOMI", "F", "906662413"),
    ("SABU", "MBAYI", "EVELYNE", "F", "812136455"),
    ("SHARADI", "NEHEMA", "LINDA", "M", ""),
    ("TSHIBANGU", "MULAJA", "MERVEILLE", "F", "821083162"),
    ("VIKA", "KAJINGA", "MIRIAM", "F", "818453789"),
    ("WETSHU", "OKONDA", "BIENVENU", "M", "816540445"),
]


class Command(BaseCommand):
    help = "Importe les apprenants Pre-Master (tronc commun) pour une année académique."

    def add_arguments(self, parser):
        parser.add_argument(
            "--annee",
            default="2024-2025",
            help="Code année académique (défaut : 2024-2025).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        annee_code = options["annee"]
        annee = AnneeAcademique.objects.filter(code=annee_code).first()
        if not annee:
            self.stderr.write(self.style.ERROR(f"Année académique {annee_code} introuvable."))
            return

        ptc = Promotion.objects.filter(code="PTC").first()
        if not ptc:
            self.stderr.write(self.style.ERROR("Promotion PTC (Pre-Master tronc commun) introuvable."))
            return

        classe = Classe.objects.filter(promotion=ptc, code="A").first()
        if not classe:
            self.stderr.write(self.style.ERROR("Classe A introuvable pour la promotion PTC."))
            return

        created_students = 0
        created_inscriptions = 0
        updated_students = 0
        ins_counter = Inscription.objects.count() + 1
        temp_counter = Student.objects.count()
        imported_students = []

        for nom, postnom, prenom, sexe, telephone in PREMASTER_ETUDIANTS:
            nom_field, prenom_field = _nom_prenom(nom, postnom, prenom)

            etudiant = Student.objects.filter(nom=nom_field, prenom=prenom_field).first()
            if etudiant:
                created = False
                update_fields = []
                if telephone and etudiant.telephone != telephone:
                    etudiant.telephone = telephone
                    update_fields.append("telephone")
                if etudiant.sexe != sexe:
                    etudiant.sexe = sexe
                    update_fields.append("sexe")
                if update_fields:
                    etudiant.save(update_fields=update_fields)
                    updated_students += 1
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
                created = True
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
            if not ins_created:
                changed = []
                if inscription.classe_id != classe.id:
                    inscription.classe = classe
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

        matricules = apply_matricule_assignments(
            build_premaster_matricule_assignments(annee, students=imported_students),
            update_email=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport Pre-Master {annee.code} — {len(PREMASTER_ETUDIANTS)} apprenant(s) traités\n"
                f"  Étudiants créés : {created_students}\n"
                f"  Étudiants mis à jour : {updated_students}\n"
                f"  Inscriptions créées : {created_inscriptions}\n"
                f"  Matricules attribués : {matricules}\n"
                f"  Classe : {classe} ({ptc.code})\n"
                f"  Total étudiants en base : {Student.objects.count()}"
            )
        )
