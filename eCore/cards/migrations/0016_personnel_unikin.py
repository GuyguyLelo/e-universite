from django.db import migrations, models


def integrer_personnel(apps, schema_editor):
    from cards.personnel_unikin_data import PERSONNEL

    Personnel = apps.get_model("cards", "Personnel")
    Grade = apps.get_model("cards", "Grade")
    Position = apps.get_model("cards", "Position")
    Category = apps.get_model("cards", "Category")

    grades = {grade.code: grade for grade in Grade.objects.all()}
    categories = {category.name: category for category in Category.objects.all()}
    positions = list(Position.objects.all())
    compteurs = {}

    for fac_code, faculte, prenom, nom, grade_code, fonction, matricule in PERSONNEL:
        service = f"Université de Kinshasa — {faculte}"[:150]
        if Personnel.objects.filter(last_name__iexact=nom, first_name__iexact=prenom).exists():
            continue
        compteurs[fac_code] = compteurs.get(fac_code, 0) + 1
        matricule = (matricule or "").strip()[:50]
        if not matricule or Personnel.objects.filter(matricule=matricule).exists():
            matricule = f"UNIKIN-{fac_code}-{compteurs[fac_code]:04d}"
        grade = grades.get(grade_code)
        corps = "Personnel scientifique" if grade_code in {"CT", "AS"} else "Personnel académique"
        position = None
        fonction_cf = (fonction or "").casefold().strip()
        if fonction_cf:
            for pos in positions:
                nom_pos = pos.name.casefold()
                if fonction_cf == nom_pos or fonction_cf.startswith(nom_pos):
                    position = pos
                    break
        Personnel.objects.create(
            first_name=prenom,
            last_name=nom,
            grade=grade,
            category=categories.get(corps),
            position=position,
            function_quality="" if position else (fonction or "")[:150],
            assignment_service=service,
            matricule=matricule,
            education_level=(grade.nom if grade else "")[:100],
            photo="",
        )


def retirer_personnel(apps, schema_editor):
    from cards.personnel_unikin_data import PERSONNEL

    Personnel = apps.get_model("cards", "Personnel")
    for _fac_code, faculte, prenom, nom, _grade, _fonction, _matricule in PERSONNEL:
        service = f"Université de Kinshasa — {faculte}"[:150]
        Personnel.objects.filter(
            last_name=nom,
            first_name=prenom,
            assignment_service=service,
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cards", "0015_grades_fonctions_unikin"),
    ]

    operations = [
        migrations.AlterField(
            model_name="personnel",
            name="photo",
            field=models.ImageField(blank=True, upload_to="personnel/photos/", verbose_name="Photo de profil"),
        ),
        migrations.RunPython(integrer_personnel, retirer_personnel),
    ]
