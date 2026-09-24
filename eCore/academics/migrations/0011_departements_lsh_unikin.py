from django.db import migrations


DEPARTEMENTS_LSH = (
    ('PHILO', 'Philosophie'),
    ('SHGPD', 'Sciences Historiques, Gestion du Patrimoine et Développement'),
    ('LCF', 'Lettres et Civilisation Françaises'),
    ('LCAFR', 'Lettres et Civilisation Africaines'),
    ('LCANG', 'Lettres et Civilisation Anglaises'),
    ('SIC', "Sciences de l'Information et de la Communication"),
    ('STD', 'Sciences et Techniques Documentaires'),
    ('LIAC', 'Langues et Informatiques Appliquées aux Affaires et au Commerce'),
    ('TRAD', 'Traduction et Interprétariat'),
    ('LASPC', 'Lettres-Arts de Spectacle Africain et Patrimoines Culturels'),
    ('ELV', 'École des Langues Vivantes'),
    ('AIA', 'Anglais et Informatique des Affaires'),
)


def seed_departements_lsh(apps, schema_editor):
    Faculte = apps.get_model('academics', 'Faculte')
    Departement = apps.get_model('academics', 'Departement')
    lettres = Faculte.objects.filter(etablissement__code='UNIKIN', code='LSH').first()
    if lettres is None:
        return
    for code, nom in DEPARTEMENTS_LSH:
        Departement.objects.get_or_create(
            faculte=lettres,
            code=code,
            defaults={'nom': nom, 'active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0010_departements_droit_unikin'),
    ]

    operations = [
        migrations.RunPython(seed_departements_lsh, migrations.RunPython.noop),
    ]
