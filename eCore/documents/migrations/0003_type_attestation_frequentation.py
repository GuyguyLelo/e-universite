from django.db import migrations


def seed_frequentation(apps, schema_editor):
    TypeAttestation = apps.get_model('documents', 'TypeAttestation')
    TypeAttestation.objects.get_or_create(
        code='frequentation',
        defaults={
            'nom': 'Attestation de fréquentation',
            'description': 'Certifie la fréquentation régulière des cours.',
            'ordre': 0,
            'active': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_attestation'),
    ]

    operations = [
        migrations.RunPython(seed_frequentation, migrations.RunPython.noop),
    ]
