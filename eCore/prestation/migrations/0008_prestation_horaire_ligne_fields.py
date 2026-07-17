from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("prestation", "0007_alter_paiemensuelle_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="prestation",
            name="heure_debut",
            field=models.TimeField(blank=True, null=True, verbose_name="Heure début"),
        ),
        migrations.AddField(
            model_name="prestation",
            name="horaire_ligne",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="prestations",
                to="prestation.horaireligne",
                verbose_name="Ligne d'horaire",
            ),
        ),
        migrations.AddField(
            model_name="prestation",
            name="jour",
            field=models.CharField(blank=True, max_length=20, verbose_name="Jour"),
        ),
        migrations.AddField(
            model_name="prestation",
            name="numero_fiche",
            field=models.CharField(blank=True, max_length=50, verbose_name="Numéro fiche"),
        ),
        migrations.AddConstraint(
            model_name="prestation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("horaire_ligne__isnull", False)),
                fields=("date_prestation", "horaire_ligne"),
                name="unique_prestation_date_horaire_ligne",
            ),
        ),
    ]
