from django.db import migrations, models


def vers_unikin(apps, schema_editor):
    Horaire = apps.get_model("prestation", "Horaire")
    Horaire.objects.filter(
        direction__in=[
            "DIRECTION DES SYSTEMES D'INFORMATION",
            "DIRECTION DES SYSTÈMES D'INFORMATION",
        ]
    ).update(direction="SECRÉTARIAT GÉNÉRAL ACADÉMIQUE")
    Horaire.objects.filter(
        ecole__in=[
            "ECOLE INFORMATIQUE DES FINANCES",
            "ÉCOLE INFORMATIQUE DES FINANCES",
        ]
    ).update(ecole="UNIVERSITÉ DE KINSHASA")
    Horaire.objects.filter(
        systeme__in=[
            "SYSTÈME LMD/RESEAU",
            "SYSTEME LMD/RESEAU",
            "SYSTÈME LMD/MASTER",
            "SYSTEME LMD/MASTER",
        ]
    ).update(systeme="SYSTÈME LMD")


class Migration(migrations.Migration):

    dependencies = [
        ("prestation", "0010_personnelbaremeinitial_quantite"),
    ]

    operations = [
        migrations.AlterField(
            model_name="horaire",
            name="direction",
            field=models.CharField(
                default="SECRÉTARIAT GÉNÉRAL ACADÉMIQUE",
                max_length=255,
                verbose_name="Direction",
            ),
        ),
        migrations.AlterField(
            model_name="horaire",
            name="ecole",
            field=models.CharField(
                default="UNIVERSITÉ DE KINSHASA",
                max_length=255,
                verbose_name="Établissement",
            ),
        ),
        migrations.AlterField(
            model_name="horaire",
            name="systeme",
            field=models.CharField(
                default="SYSTÈME LMD",
                max_length=255,
                verbose_name="Système",
            ),
        ),
        migrations.RunPython(vers_unikin, migrations.RunPython.noop),
    ]
