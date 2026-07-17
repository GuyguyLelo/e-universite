from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prestation", "0009_personnelbaremeinitial"),
    ]

    operations = [
        migrations.AddField(
            model_name="personnelbaremeinitial",
            name="quantite",
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
                verbose_name="Quantité",
            ),
        ),
    ]
