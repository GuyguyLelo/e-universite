import uuid

from django.db import migrations, models


def remplir_codes(apps, schema_editor):
    Personnel = apps.get_model("cards", "Personnel")
    for person in Personnel.objects.all().iterator():
        person.code_unique = uuid.uuid4()
        person.save(update_fields=["code_unique"])


class Migration(migrations.Migration):

    dependencies = [
        ("cards", "0016_personnel_unikin"),
    ]

    operations = [
        migrations.AddField(
            model_name="personnel",
            name="code_unique",
            field=models.UUIDField(editable=False, null=True, verbose_name="Code unique"),
        ),
        migrations.RunPython(remplir_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="personnel",
            name="code_unique",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Code unique"),
        ),
    ]
