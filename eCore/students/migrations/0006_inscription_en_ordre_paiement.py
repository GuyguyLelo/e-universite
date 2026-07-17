from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0005_matricule_format'),
    ]

    operations = [
        migrations.AddField(
            model_name='inscription',
            name='en_ordre_paiement',
            field=models.BooleanField(default=False, verbose_name='En ordre de paiement'),
        ),
    ]
