from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0007_inscription_statut_abandon'),
    ]

    operations = [
        migrations.AddField(
            model_name='inscription',
            name='date_abandon',
            field=models.DateField(blank=True, null=True, verbose_name="Date d'abandon"),
        ),
        migrations.AddField(
            model_name='inscription',
            name='motif_abandon',
            field=models.TextField(blank=True, null=True, verbose_name="Motif d'abandon"),
        ),
    ]
