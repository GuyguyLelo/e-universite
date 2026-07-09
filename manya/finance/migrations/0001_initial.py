from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='MotifPaiement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='Code')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('montant', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='0 = montant variable selon le cas',
                    max_digits=12,
                    verbose_name='Montant par défaut (USD)',
                )),
                ('ordre', models.PositiveIntegerField(default=1, verbose_name="Ordre d'affichage")),
                ('active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Motif de paiement',
                'verbose_name_plural': 'Motifs de paiement',
                'ordering': ['ordre', 'nom'],
            },
        ),
    ]
