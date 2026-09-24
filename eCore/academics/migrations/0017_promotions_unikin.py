from django.db import migrations


# Durées publiées par la Faculté de Médecine (unikin.ac.cd) :
# biomédicale / médecine humaine = 7 ans, médecine physique = 5 ans.
# Les autres programmes ouverts au grade de licence LMD comptent 3 ans.
DUREES = {
    ('MED', 'MHUM'): 7,
    ('MED', 'MPR'): 5,
}

ANNEES = {
    1: '1ʳᵉ année',
    2: '2ᵉ année',
    3: '3ᵉ année',
    4: '4ᵉ année',
    5: '5ᵉ année',
    6: '6ᵉ année',
    7: '7ᵉ année',
}


def seed_promotions(apps, schema_editor):
    Filiere = apps.get_model('academics', 'Filiere')
    Promotion = apps.get_model('academics', 'Promotion')
    filieres = Filiere.objects.filter(
        faculte__etablissement__code='UNIKIN',
    ).select_related('faculte')
    for filiere in filieres:
        duree = DUREES.get((filiere.faculte.code, filiere.code), 3)
        for ordre in range(1, duree + 1):
            Promotion.objects.get_or_create(
                filiere=filiere,
                code=f'A{ordre}',
                defaults={
                    'nom': ANNEES[ordre],
                    'ordre': ordre,
                    'active': True,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0016_classe_local_optionnel'),
    ]

    operations = [
        migrations.RunPython(seed_promotions, migrations.RunPython.noop),
    ]
