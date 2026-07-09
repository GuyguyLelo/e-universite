from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_motifpaiement_sans_promotion'),
    ]

    operations = [
        migrations.AddField(
            model_name='motifpaiement',
            name='devise',
            field=models.CharField(
                choices=[('USD', 'Dollars (USD)'), ('CDF', 'Francs congolais (CDF)')],
                default='USD',
                max_length=3,
                verbose_name='Devise',
            ),
        ),
        migrations.AlterField(
            model_name='motifpaiement',
            name='montant',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='0 = montant variable selon le cas',
                max_digits=12,
                verbose_name='Montant',
            ),
        ),
    ]
