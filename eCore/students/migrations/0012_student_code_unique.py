import uuid

from django.db import migrations, models


def remplir_codes(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    for student in Student.objects.all().iterator():
        student.code_unique = uuid.uuid4()
        student.save(update_fields=["code_unique"])


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0011_etablissement_national"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="code_unique",
            field=models.UUIDField(editable=False, null=True, verbose_name="Code unique"),
        ),
        migrations.RunPython(remplir_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="student",
            name="code_unique",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Code unique"),
        ),
    ]
