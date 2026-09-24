from django.db import migrations, models
import django.db.models.deletion


GRADES = (
    ("PE", "Professeur émérite", "academique", 1),
    ("PO", "Professeur ordinaire", "academique", 2),
    ("PR", "Professeur", "academique", 3),
    ("PA", "Professeur associé", "academique", 4),
    ("DR", "Docteur", "academique", 5),
    ("CT", "Chef de travaux", "scientifique", 6),
    ("AS", "Assistant", "scientifique", 7),
)

FONCTIONS = (
    "Recteur",
    "Secrétaire général académique",
    "Secrétaire général administratif",
    "Secrétaire général de la recherche",
    "Administrateur du budget",
    "Doyen",
    "Vice-doyen chargé de l'enseignement",
    "Vice-doyen chargé de la recherche",
    "Chef de département",
    "Secrétaire académique",
    "Secrétaire administratif et financier",
)

CATEGORIES = (
    "Personnel académique",
    "Personnel scientifique",
    "Personnel administratif",
)

ALIAS_GRADES = {
    "pe": "PE",
    "p.e.": "PE",
    "po": "PO",
    "p.o.": "PO",
    "p.o": "PO",
    "pa": "PA",
    "p.a.": "PA",
    "p.a": "PA",
    "pr": "PR",
    "p": "PR",
    "professeur full": "PR",
    "professeur émérite": "PE",
    "professeur emerite": "PE",
    "professeur ordinaire": "PO",
    "professeur": "PR",
    "professeur associé": "PA",
    "professeur associe": "PA",
    "docteur": "DR",
    "chef de travaux": "CT",
    "assistant": "AS",
}


def integrer_grades_fonctions(apps, schema_editor):
    Grade = apps.get_model("cards", "Grade")
    Personnel = apps.get_model("cards", "Personnel")
    Position = apps.get_model("cards", "Position")
    Category = apps.get_model("cards", "Category")

    par_code = {}
    for code, nom, corps, ordre in GRADES:
        grade = Grade.objects.create(code=code, nom=nom, corps=corps, ordre=ordre)
        par_code[code] = grade

    for person in Personnel.objects.exclude(grade_ancien=""):
        cle = (person.grade_ancien or "").strip().casefold()
        code = ALIAS_GRADES.get(cle)
        grade = par_code.get(code) if code else None
        if grade is not None:
            person.grade_id = grade.pk
            person.save(update_fields=["grade"])

    for nom in FONCTIONS:
        Position.objects.get_or_create(name=nom)
    for nom in CATEGORIES:
        Category.objects.get_or_create(name=nom)


class Migration(migrations.Migration):

    dependencies = [
        ("cards", "0014_alter_card_public_token_native_uuid"),
    ]

    operations = [
        migrations.CreateModel(
            name="Grade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=10, unique=True, verbose_name="Code")),
                ("nom", models.CharField(max_length=100, unique=True, verbose_name="Grade")),
                ("corps", models.CharField(choices=[("academique", "Personnel académique"), ("scientifique", "Personnel scientifique")], max_length=20, verbose_name="Corps")),
                ("ordre", models.PositiveSmallIntegerField(default=1, verbose_name="Ordre")),
            ],
            options={
                "verbose_name": "Grade",
                "verbose_name_plural": "Grades",
                "ordering": ["ordre", "nom"],
            },
        ),
        migrations.RenameField(
            model_name="personnel",
            old_name="grade",
            new_name="grade_ancien",
        ),
        migrations.AddField(
            model_name="personnel",
            name="grade",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="personnels",
                to="cards.grade",
                verbose_name="Grade",
            ),
        ),
        migrations.AlterModelOptions(
            name="position",
            options={
                "ordering": ["name"],
                "verbose_name": "Poste / Fonction",
                "verbose_name_plural": "Postes / Fonctions",
            },
        ),
        migrations.RunPython(integrer_grades_fonctions, migrations.RunPython.noop),
    ]
