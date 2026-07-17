"""
Import de la maquette LMD — Semestre 7, filière CSI (Conception des SI).
Usage: python manage.py import_maquette_csi_s7 [--clear]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import Filiere, Semestre, UniteEnseignement, ElementConstitutif

# Maquette officielle Semestre 7 — CSI
CSI_S7_MAQUETTE = [
    {
        'ordre': 1,
        'code': 'ALG2171',
        'nom': 'Progiciel de Gestion Intégré (PGI)',
        'credits': Decimal('4'),
        'categorie': 'A',
    },
    {
        'ordre': 2,
        'code': 'GFC2172',
        'nom': 'Gestion financière et contrôle de gestion',
        'credits': Decimal('3'),
        'categorie': 'B',
    },
    {
        'ordre': 3,
        'code': 'ING2173',
        'nom': 'Modélisation des SI (UML) avancée',
        'credits': Decimal('6'),
        'categorie': 'A',
    },
    {
        'ordre': 7,
        'code': 'BDD2175',
        'nom': 'Bases de Données avancées et NoSQL',
        'credits': Decimal('4'),
        'categorie': 'A',
    },
    {
        'ordre': 8,
        'code': 'LAN2176',
        'nom': 'Langues et communication',
        'credits': Decimal('6'),
        'categorie': 'A',
        'ecs': [
            {'ordre': 1, 'code': 'LAN2176-EC1', 'nom': 'Anglais technique', 'credits': Decimal('3')},
            {'ordre': 2, 'code': 'LAN2176-EC2', 'nom': 'Communication Scientifique', 'credits': Decimal('3')},
        ],
    },
    {
        'ordre': 11,
        'code': 'SYS2177',
        'nom': "Système d'Objets Réparti",
        'credits': Decimal('4'),
        'categorie': 'A',
    },
    {
        'ordre': 12,
        'code': 'RSI2178',
        'nom': 'Recherche Scientifique en Informatique de gestion',
        'credits': Decimal('3'),
        'categorie': 'B',
    },
]


class Command(BaseCommand):
    help = "Importe la maquette du Semestre 7 pour la filière CSI."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprime les UE/EC CSI du semestre 7 avant import',
        )

    def handle(self, *args, **options):
        filiere = Filiere.objects.filter(code='CSI').first()
        if not filiere:
            self.stderr.write(self.style.ERROR("Filière CSI introuvable."))
            return

        semestre = self._get_or_fix_semestre_s7()

        if options['clear']:
            deleted_ec, _ = ElementConstitutif.objects.filter(
                ue__semestre=semestre, ue__filiere=filiere
            ).delete()
            deleted_ue, _ = UniteEnseignement.objects.filter(
                semestre=semestre, filiere=filiere
            ).delete()
            self.stdout.write(
                self.style.WARNING(f"Supprimé : {deleted_ue} UE, {deleted_ec} EC (CSI S7).")
            )

        with transaction.atomic():
            ue_count = 0
            ec_count = 0
            total_credits = Decimal('0')

            for item in CSI_S7_MAQUETTE:
                ue, _ = UniteEnseignement.objects.update_or_create(
                    semestre=semestre,
                    filiere=filiere,
                    code=item['code'],
                    defaults={
                        'nom': item['nom'],
                        'credits_ects': item['credits'],
                        'coefficient': Decimal('1.00'),
                        'seuil_validation': Decimal('10.00'),
                        'compensation_autorisee': True,
                        'capitalisable': True,
                        'categorie': item['categorie'],
                        'ordre': item['ordre'],
                        'active': True,
                    },
                )
                ue_count += 1
                total_credits += item['credits']

                ecs_data = item.get('ecs')
                if ecs_data:
                    for ec_item in ecs_data:
                        ElementConstitutif.objects.update_or_create(
                            ue=ue,
                            code=ec_item['code'],
                            defaults={
                                'nom': ec_item['nom'],
                                'credits_ects': ec_item['credits'],
                                'coefficient': Decimal('1.00'),
                                'seuil_validation': Decimal('10.00'),
                                'compensation_autorisee': True,
                                'capitalisable': True,
                                'ordre': ec_item['ordre'],
                                'active': True,
                            },
                        )
                        ec_count += 1
                else:
                    ElementConstitutif.objects.update_or_create(
                        ue=ue,
                        code=item['code'],
                        defaults={
                            'nom': item['nom'],
                            'credits_ects': item['credits'],
                            'coefficient': Decimal('1.00'),
                            'seuil_validation': Decimal('10.00'),
                            'compensation_autorisee': True,
                            'capitalisable': True,
                            'ordre': 1,
                            'active': True,
                        },
                    )
                    ec_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Maquette CSI S7 importée : {ue_count} UE, {ec_count} EC, "
            f"{total_credits} crédits ECTS (attendu : 30)."
        ))

    def _get_or_fix_semestre_s7(self):
        semestre = Semestre.objects.filter(code='S7').first()
        if semestre:
            if semestre.numero != 7:
                semestre.numero = 7
                semestre.nom = 'Semestre 7'
                semestre.credits_ects = 30
                semestre.save(update_fields=['numero', 'nom', 'credits_ects'])
            return semestre

        semestre, _ = Semestre.objects.get_or_create(
            numero=7,
            defaults={
                'code': 'S7',
                'nom': 'Semestre 7',
                'credits_ects': 30,
                'active': True,
            },
        )
        return semestre
