"""
Met à jour les téléphones étudiants depuis la liste officielle (préfixe 0).
"""
import re
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from config.management.commands.import_etudiants_master1 import _nom_prenom
from students.models import Student

# Liste extraite du fichier Excel — (NOM, POSTNOM, PRENOM, TELEPHONE)
TELEPHONE_ROWS = [
    ("ABDALA", "NOTIA", "RUTH", "857630368"),
    ("ABIZI", "EDJOKOLA", "MIRADI", "893833971"),
    ("AMISI", "ASSANGO", "LIONEL", "890237987"),
    ("BADRIYO", "MARINDO", "KING", "981808556"),
    ("BAMBUSE", "ENGEMBELE", "ZACHARIE", "822000054"),
    ("BELE", "NGUMA", "DANIEL", "978923254"),
    ("BOLOLA", "MALOYI", "RALPH", "820623339"),
    ("BONGOTA", "EMEKA", "HERITIER", "810478430"),
    ("BONYAMBALA", "YAKUSU", "SAEL", "838825978"),
    ("BUZITU", "KEITA", "SERDY", "830778696"),
    ("DIKIZEYIKO", "MAKIESE", "BLESSING", "847194155"),
    ("ESTOL", "MOKIMO", "GRACE", "973400102"),
    ("FETA", "FADI NKASA", "HOBLESSE", "826249964"),
    ("GINENGA", "SELE", "JERMIE", "990719380"),
    ("ISEMOLI", "ELONGO", "JAELLE", "972713006"),
    ("IYAMA", "LAKUNG", "SANTA", "997933016"),
    ("KADIMA", "NGOYI", "PANIEL", "975191705"),
    ("KAKESA", "MPONO", "GOEL", "845024983"),
    ("KALONDA", "WUTSHU", "GEORGES", "823979834"),
    ("KALONJI", "MUKUNA", "FRANCK", "810007093"),
    ("KAMUNYI", "KANKONDE", "NARCISSE", "829552228"),
    ("KAMWANYA", "MULUMBA", "BENEDICTE", "833087563"),
    ("KANDE", "BABADI", "NATHAN", "824202218"),
    ("KANKOLONGO", "KABENGELE", "CAROL", "843213331"),
    ("KATSHAY", "MPENGO", "EXAUCEE", "814912405"),
    ("KAWELE", "MBEMBI", "KEVIN", "825866941"),
    ("KAZADI", "KONGOLO", "HERVE", "846846983"),
    ("KHUBA", "MAVINGA", "ELYON", "973812680"),
    ("KIANGEBENI", "MATONDO", "HERMINE", "980657709"),
    ("KOMBO", "IWEWE", "MERVEILLE", "993563092"),
    ("LOMBOTO", "BOLONGO", "HENOC", "978481920"),
    ("LUEMBA", "MBEDIKA", "JORDANE", "815829718"),
    ("LUFIY", "MAFUTA", "MERCE", "822685864"),
    ("MABONDO", "NSATUKANDA", "BENEDICTE", "971972586"),
    ("MAKUZULU", "NZAZI", "JUNIOR", "812668309"),
    ("MALONDA", "DODY", "JEREMIE-SAGAC", "850828229"),
    ("MAMBA", "BADIBANGA", "DEBORAH", "981576339"),
    ("MANSIANGI", "MBALA", "GRACIA", "899907136"),
    ("MASAMUNA", "KYUNDU", "DJEBIE", "850675669"),
    ("MASUDI", "MIGEYA", "JACQUES", "816262398"),
    ("MBAYO", "MUKALAMUSI", "AMEDE", "821707309"),
    ("META", "KADIAMBA", "GLOIRE", "905076191"),
    ("METHA", "MABITA", "BERNATHAN", "977512448"),
    ("MPUTU", "IFOSO", "MOSES", "897939027"),
    ("MUHETO", "MADISEKULA", "GRADIE", "816101110"),
    ("MUJINGA", "KAZOVU", "PAPY", "815081894"),
    ("MUSASA", "LOTIKA", "NATHAN", "897107830"),
    ("MWANZA", "MBUYI", "BENEDICTE", "984169960"),
    ("NGALULA", "ILUNGA", "MARTHE", "973524282"),
    ("NGONGO", "SELE", "CHARLENE", "816880477"),
    ("NSIMIRE", "CHIRUZA", "VENANCYA", "822689322"),
    ("NSINGI", "NDOMBASI", "JEREMIE", "825060071"),
    ("NSUALA", "BAKELUBA", "GRACE", "824062626"),
    ("NTUMBA", "LUSHIKU", "MICHEE", "813920883"),
    ("NYATH", "IYOLO", "WALTER", "812700875"),
    ("NZUMI", "KAM", "PERRIN", "812424210"),
    ("OMALOWETE", "MANYA", "ALPHONSE", "859178041"),
    ("OTEMANYANGA", "TAKENGE", "RACHEL", "813827260"),
    ("PALAKI", "BOLAWELO", "PLATINI", "822092000"),
    ("PAY", "KAPWANGA", "COVO", "896346362"),
    ("PINDU", "PINDU", "DJO", "812645617"),
    ("RAMAZANI", "ISSA", "NAOMI", "906662413"),
    ("SABU", "MBAYI", "EVELYNE", "812136455"),
    ("SETH", "MASUDI", "USHINDI", "818808469"),
    ("SHUKURU", "KUBUYA", "TILAMOVIC", "894181981"),
    ("VIKA", "KAJINGA", "MIRIAM", "818453789"),
    ("WAKIMESA", "KIMPILAMPILA", "GUY", "892204971"),
    ("WANGE", "MBO", "EVODIE", "840853863"),
]

# Correspondances nom Excel → nom en base
NOM_VARIANTS = {
    ("BAMBUSE", "ENGEMBELE"): [("DAMBUSE", "ENGEMBELE")],
    ("BUZITU", "KEITA"): [("DIZITU", "KEITA")],
    ("IYAMA", "LAKUNG"): [("IYAMA", "LUKUNG")],
    ("KALONDA", "WUTSHU"): [("KALONDA", "WETSHU")],
    ("KAZADI", "KONGOLO"): [("KAZADI", "KONCOLO")],
    ("LUFIY", "MAFUTA"): [("LUHY", "MAFUTA")],
    ("MASAMUNA", "KYUNDU"): [("MASAMUNA", "KYUNGU")],
    ("FETA", "FADI NKASA"): [("FETA", "NKASA")],
    ("GINENGA", "SELE"): [("GINENGA", "MWAMBA")],
    ("NGONGO", "SELE"): [("NCONGO", "SELE")],
    ("NZUMI", "KAM"): [("NZUMBI", "KAMI")],
    ("PINDU", "PINDU"): [("PINDU", "PINDI")],
    ("WAKIMESA", "KIMPILAMPILA"): [("WAKIMESA", "KIMPALAMPALA")],
}


def _normalize(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().upper()


def _format_phone(raw):
    digits = re.sub(r"\D", "", str(raw or ""))
    if not digits:
        return None
    if digits.startswith("0"):
        return digits
    return f"0{digits}"


def _nom_keys(nom, postnom):
    keys = [(nom, postnom)]
    variant = NOM_VARIANTS.get((nom, postnom))
    if variant:
        keys.extend(variant)
    return keys


def _find_student(nom, postnom, prenom):
    for n, p in _nom_keys(nom, postnom):
        if p:
            student = Student.objects.filter(nom__iexact=n, prenom__iexact=p).first()
            if student:
                return student

        full_nom_only = f"{n} {p}".strip() if p else n

        matches = list(Student.objects.filter(nom__iexact=full_nom_only))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1 and prenom:
            prenom_n = _normalize(prenom)
            for student in matches:
                sp = _normalize(student.prenom)
                if prenom_n == sp or prenom_n in sp or sp in prenom_n:
                    return student

        full_nom, prenom_field = _nom_prenom(n, p, prenom)
        student = Student.objects.filter(nom=full_nom, prenom=prenom_field).first()
        if student:
            return student

        if not p:
            matches = list(Student.objects.filter(nom__iexact=n))
            if len(matches) == 1:
                return matches[0]

        fuzzy = [
            s for s in Student.objects.filter(nom__istartswith=n)
            if not p or _normalize(p) in _normalize(s.nom)
        ]
        if len(fuzzy) == 1:
            return fuzzy[0]

    return None


class Command(BaseCommand):
    help = "Complète les numéros de téléphone (préfixe 0) depuis la liste Excel."

    @transaction.atomic
    def handle(self, *args, **options):
        updated = 0
        skipped = 0
        missing = []

        for nom, postnom, prenom, raw_phone in TELEPHONE_ROWS:
            phone = _format_phone(raw_phone)
            if not phone:
                skipped += 1
                continue

            student = _find_student(nom, postnom, prenom)
            if not student:
                missing.append(f"{nom} {postnom} {prenom}".strip())
                continue

            if student.telephone != phone:
                student.telephone = phone
                student.save(update_fields=["telephone"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} téléphone(s) mis à jour."))
        if skipped:
            self.stdout.write(self.style.WARNING(f"{skipped} ligne(s) sans numéro ignorée(s)."))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"{len(missing)} étudiant(s) non trouvé(s) : {', '.join(missing[:8])}"
                + ("…" if len(missing) > 8 else "")
            ))

        without = Student.objects.filter(telephone__isnull=True) | Student.objects.filter(telephone="")
        self.stdout.write(f"Étudiants encore sans téléphone : {without.count()}")
