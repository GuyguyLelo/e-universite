from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0006_inscription_en_ordre_paiement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inscription',
            name='statut',
            field=models.CharField(
                choices=[
                    ('preinscrit', 'Pré-inscrit'),
                    ('inscrit', 'Inscrit'),
                    ('reinscrit', 'Réinscrit'),
                    ('redoublant', 'Redoublant'),
                    ('transfert', 'Transfert'),
                    ('desinscrit', 'Désinscrit'),
                    ('abandon', 'Abandon'),
                ],
                default='preinscrit',
                max_length=20,
                verbose_name='Statut',
            ),
        ),
    ]
