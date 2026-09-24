from django.db import migrations


# Options distinctes du nom du département, publiées par la faculté
# ou par le secrétariat académique (programmes 2026-2027).
OPTIONS = {
    ('DROIT', 'DEA'): (
        ('DAFF', 'Droit des affaires'),
        ('DESO', 'Droit économique et social'),
        ('DFIS', 'Droit fiscal'),
        ('DTSS', 'Droit du travail et de la sécurité sociale'),
    ),
    ('DROIT', 'DPI'): (
        ('DADM', 'Droit administratif'),
        ('DCON', 'Droit constitutionnel'),
    ),
    ('LSH', 'SHGPD'): (
        ('HIST', 'Histoire'),
        ('GEOG', 'Géographie'),
        ('SHIS', 'Sciences historiques'),
    ),
    ('LSH', 'LCAFR'): (
        ('LLAF', 'Langues et littératures africaines'),
    ),
    ('LSH', 'LCANG'): (
        ('LLAN', 'Langues et littératures anglaises'),
    ),
    ('LSH', 'LCF'): (
        ('LCLA', 'Lettres et langues classiques'),
    ),
    ('LSH', 'STD'): (
        ('BIBL', 'Bibliothéconomie et sciences documentaires'),
    ),
    ('MED', 'SBAS'): (
        ('MHUM', 'Médecine humaine'),
        ('SBIO', 'Sciences biomédicales'),
    ),
    ('MED', 'GYNE'): (
        ('GYOB', 'Gynécologie-obstétrique'),
    ),
    ('MED', 'ESPK'): (
        ('SPUB', 'Santé publique'),
    ),
    ('FPSE', 'PSY'): (
        ('PSYC', 'Psychologie clinique'),
    ),
    ('FPSE', 'GEOT'): (
        ('PTO', 'Psychologie du travail et des organisations'),
    ),
    ('FPSE', 'SEDU'): (
        ('SPSY', 'Sciences psychopédagogiques'),
    ),
    ('FSSAP', 'SPA'): (
        ('APUB', 'Administration publique'),
    ),
    ('POLY', 'GCIV'): (
        ('HYDR', 'Hydraulique'),
        ('ARCH', 'Architecture et urbanisme'),
        ('GEOM', 'Géomatique et topographie'),
    ),
    ('POLY', 'GEI'): (
        ('GELEC', 'Génie électrique'),
        ('GELE', 'Génie électronique'),
        ('GINFO', 'Génie informatique'),
        ('GTEL', 'Génie des télécommunications'),
    ),
    ('POLY', 'GMEC'): (
        ('GIND', 'Génie industriel'),
        ('GMET', 'Génie métallurgique'),
        ('GMIN', 'Génie des mines'),
        ('GCHI', 'Génie chimique'),
    ),
    ('FMV', 'ZOO'): (
        ('PANI', 'Productions animales'),
    ),
    ('FMV', 'CLIN'): (
        ('MVET', 'Médecine vétérinaire'),
        ('SASP', 'Santé animale et santé publique vétérinaire'),
    ),
    ('FPGEN', 'EXPRO'): (
        ('EXPL', 'Exploration'),
        ('PROD', 'Production'),
    ),
    ('FPGEN', 'GEEN'): (
        ('GENE', 'Génie énergétique'),
        ('GENV', 'Génie environnemental'),
    ),
}


def seed_filieres(apps, schema_editor):
    Departement = apps.get_model('academics', 'Departement')
    Filiere = apps.get_model('academics', 'Filiere')
    departements = Departement.objects.filter(
        faculte__etablissement__code='UNIKIN',
    ).select_related('faculte')
    for departement in departements:
        Filiere.objects.get_or_create(
            departement=departement,
            code=departement.code,
            defaults={
                'nom': departement.nom,
                'faculte': departement.faculte,
                'active': True,
            },
        )
        extras = OPTIONS.get((departement.faculte.code, departement.code), ())
        for code, nom in extras:
            Filiere.objects.get_or_create(
                departement=departement,
                code=code,
                defaults={
                    'nom': nom,
                    'faculte': departement.faculte,
                    'active': True,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0014_filiere_departement'),
    ]

    operations = [
        migrations.RunPython(seed_filieres, migrations.RunPython.noop),
    ]
