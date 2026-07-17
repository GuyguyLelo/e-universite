# Generated manually for unified matricule format

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0009_alter_student_numero_etudiant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='numero_etudiant',
            field=models.CharField(
                max_length=20,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message=(
                            "Matricule invalide. Année + n° d'ordre sur 4 chiffres "
                            '(ex. 20260001), sans distinction de filière.'
                        ),
                        regex=r'^(\d{8}|\d{7}|\d{4}[RC]\d{3})$',
                    ),
                ],
                verbose_name='Numéro étudiant',
            ),
        ),
    ]
