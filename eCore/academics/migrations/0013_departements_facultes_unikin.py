from django.db import migrations


DEPARTEMENTS = {
    'SEG': (
        ('BASS', 'Banque et assurances'),
        ('CINT', 'Commerce international'),
        ('COMP', 'Comptabilité'),
        ('FISC', 'Fiscalité'),
        ('GRH', 'Gestion des ressources humaines'),
        ('GFIN', 'Gestion financière'),
        ('IGEST', 'Informatique de gestion'),
        ('MORG', 'Management et organisation'),
        ('MARK', 'Marketing'),
        ('SCF', 'Sciences commerciales et financières'),
        ('GEST', 'Sciences de gestion'),
        ('SECO', 'Sciences économiques'),
        ('EDEV', 'Économie du développement'),
        ('EMAT', 'Économie mathématique'),
        ('EMON', 'Économie monétaire et internationale'),
        ('ERUR', 'Économie rurale'),
    ),
    'FSSAP': (
        ('SPA', 'Sciences politiques et administratives'),
        ('TRAV', 'Sciences du travail'),
        ('SOCIO', 'Sociologie'),
        ('RI', 'Relations internationales'),
        ('ANTH', 'Anthropologie'),
    ),
    'FPSE': (
        ('PSY', 'Psychologie'),
        ('SEDU', "Sciences de l'éducation"),
        ('GEOT', 'Gestion des entreprises et organisation du travail'),
        ('AGREG', 'Agrégation'),
    ),
    'SCI': (
        ('BIO', 'Biologie'),
        ('CHIM', 'Chimie'),
        ('GEO', 'Géologie'),
        ('GEOSC', 'Géosciences'),
        ('INFO', 'Informatique'),
        ('MATH', 'Mathématiques'),
        ('PHYS', 'Physique'),
        ('SENV', "Sciences de l'environnement"),
        ('STAT', 'Statistique'),
    ),
    'POLY': (
        ('SBAS', 'Sciences de base'),
        ('GCIV', 'Génie civil'),
        ('GEI', 'Génie électrique et informatique'),
        ('GMEC', 'Génie mécanique'),
    ),
    'PHARM': (
        ('BCLI', 'Biologie clinique'),
        ('CTHER', 'Chimie thérapeutique'),
        ('CQMED', 'Contrôle de qualité des médicaments'),
        ('PGAL', 'Pharmacie galénique'),
        ('PHOSP', 'Pharmacie hospitalière'),
        ('PCOG', 'Pharmacognosie'),
        ('SPHARM', 'Sciences pharmaceutiques'),
        ('TOXI', 'Toxicologie'),
    ),
    'AGRO': (
        ('AGEN', 'Agronomie générale'),
        ('CHIA', 'Chimie et industries agricoles'),
        ('DVEG', 'Défense des végétaux (phytopathologie)'),
        ('DRUR', 'Développement rural'),
        ('EFOR', 'Eaux et forêts'),
        ('EGRN', 'Environnement et gestion des ressources naturelles'),
        ('NUTA', 'Nutrition et technologie alimentaire'),
        ('PHYT', 'Phytotechnie'),
        ('SSOL', 'Sciences du sol'),
        ('ZOO', 'Zootechnie'),
        ('EAGR', 'Économie agricole'),
    ),
    'FMV': (
        ('SBAS', 'Sciences de base'),
        ('ZOO', 'Zootechnie'),
        ('PREC', 'Sciences précliniques'),
        ('CLIN', 'Sciences cliniques'),
    ),
    'FPGEN': (
        ('SBAS', 'Sciences de base'),
        ('EXPRO', 'Exploration-production'),
        ('GECO', 'Gestion et économie'),
        ('PETRO', 'Pétrochimie et raffinage'),
        ('GEEN', 'Génie énergétique et environnemental'),
    ),
    'DENT': (
        ('CBMF', 'Chirurgie buccale et maxillo-faciale'),
        ('MDENT', 'Médecine dentaire'),
    ),
}


def seed_departements_unikin(apps, schema_editor):
    Etablissement = apps.get_model('config', 'Etablissement')
    Faculte = apps.get_model('academics', 'Faculte')
    Departement = apps.get_model('academics', 'Departement')
    unikin = Etablissement.objects.filter(code='UNIKIN').first()
    if unikin is None:
        return
    Faculte.objects.get_or_create(
        etablissement=unikin,
        code='DENT',
        defaults={
            'nom': 'Faculté de Médecine Dentaire',
            'active': True,
        },
    )
    for faculte_code, departements in DEPARTEMENTS.items():
        faculte = Faculte.objects.filter(etablissement=unikin, code=faculte_code).first()
        if faculte is None:
            continue
        for code, nom in departements:
            Departement.objects.get_or_create(
                faculte=faculte,
                code=code,
                defaults={'nom': nom, 'active': True},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0012_departements_med_unikin'),
    ]

    operations = [
        migrations.RunPython(seed_departements_unikin, migrations.RunPython.noop),
    ]
