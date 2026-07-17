from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_type_attestation_frequentation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='typedocumentgenere',
            name='code',
            field=models.CharField(max_length=40, unique=True, verbose_name='Code'),
        ),
    ]
