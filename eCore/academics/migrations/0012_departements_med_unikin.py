from django.db import migrations


DEPARTEMENTS_MED = (
    ('CHIR', 'Chirurgie'),
    ('CNPP', 'Centre Neuro-Psycho-Pathologique'),
    ('ESPK', 'École de Santé Publique de Kinshasa'),
    ('GYNE', 'Gynécologie'),
    ('MINT', 'Médecine interne'),
    ('MPR', 'Médecine physique et réadaptation'),
    ('ODON', 'Odonto-stomatologie'),
    ('SBAS', 'Sciences de base'),
    ('MTROP', 'Médecine tropicale, maladies infectieuses et parasitaires'),
)


def seed_departements_med(apps, schema_editor):
    Faculte = apps.get_model('academics', 'Faculte')
    Departement = apps.get_model('academics', 'Departement')
    medecine = Faculte.objects.filter(etablissement__code='UNIKIN', code='MED').first()
    if medecine is None:
        return
    for code, nom in DEPARTEMENTS_MED:
        Departement.objects.get_or_create(
            faculte=medecine,
            code=code,
            defaults={'nom': nom, 'active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0011_departements_lsh_unikin'),
    ]

    operations = [
        migrations.RunPython(seed_departements_med, migrations.RunPython.noop),
    ]
