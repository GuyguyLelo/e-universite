from django.db import migrations, models
import django.db.models.deletion


def assign_default_promotion(apps, schema_editor):
    MotifPaiement = apps.get_model('finance', 'MotifPaiement')
    Promotion = apps.get_model('academics', 'Promotion')
    promotion = Promotion.objects.order_by('filiere__code', 'ordre', 'code').first()
    if promotion:
        MotifPaiement.objects.filter(promotion__isnull=True).update(promotion=promotion)


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='motifpaiement',
            name='code',
            field=models.CharField(max_length=20, verbose_name='Code'),
        ),
        migrations.AddField(
            model_name='motifpaiement',
            name='promotion',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='motifs_paiement',
                to='academics.promotion',
                verbose_name='Promotion',
            ),
        ),
        migrations.RunPython(assign_default_promotion, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='motifpaiement',
            name='promotion',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='motifs_paiement',
                to='academics.promotion',
                verbose_name='Promotion',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together={('promotion', 'code')},
        ),
        migrations.AlterModelOptions(
            name='motifpaiement',
            options={
                'ordering': ['promotion__filiere', 'promotion__ordre', 'ordre', 'nom'],
                'verbose_name': 'Motif de paiement',
                'verbose_name_plural': 'Motifs de paiement',
            },
        ),
    ]
