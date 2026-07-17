from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cards", "0011_alter_card_public_token"),
        ("prestation", "0008_prestation_horaire_ligne_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PersonnelBaremeInitial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "bareme",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="personnels_initiaux",
                        to="prestation.baremeprestation",
                        verbose_name="Barème",
                    ),
                ),
                (
                    "personnel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="baremes_initiaux_liens",
                        to="cards.personnel",
                        verbose_name="Personnel",
                    ),
                ),
            ],
            options={
                "verbose_name": "Barème initial du personnel",
                "verbose_name_plural": "Barèmes initiaux du personnel",
                "ordering": ["personnel", "bareme__categorie", "bareme__ordre", "bareme__intitule"],
            },
        ),
        migrations.AddConstraint(
            model_name="personnelbaremeinitial",
            constraint=models.UniqueConstraint(
                fields=("personnel", "bareme"),
                name="unique_personnel_bareme_initial",
            ),
        ),
    ]
