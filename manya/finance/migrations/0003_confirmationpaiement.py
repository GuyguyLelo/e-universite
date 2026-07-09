from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('students', '0006_inscription_en_ordre_paiement'),
        ('finance', '0002_motifpaiement_promotion'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfirmationPaiement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('confirme', models.BooleanField(default=True, verbose_name='Confirmé')),
                ('date_confirmation', models.DateTimeField(auto_now=True, verbose_name='Date de confirmation')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirme_par', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='confirmations_paiement_effectuees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Confirmé par',
                )),
                ('inscription', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='confirmations_paiement',
                    to='students.inscription',
                    verbose_name='Inscription',
                )),
                ('motif_paiement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='confirmations',
                    to='finance.motifpaiement',
                    verbose_name='Motif de paiement',
                )),
            ],
            options={
                'verbose_name': 'Confirmation de paiement',
                'verbose_name_plural': 'Confirmations de paiement',
                'ordering': ['-date_confirmation'],
                'unique_together': {('inscription', 'motif_paiement')},
            },
        ),
    ]
