from django.db import migrations, models
import django.db.models.deletion


def backfill_annee_contexte(apps, schema_editor):
    MotifPaiement = apps.get_model('finance', 'MotifPaiement')
    AnneeAcademique = apps.get_model('academics', 'AnneeAcademique')
    annee = (
        AnneeAcademique.objects.filter(active=True).first()
        or AnneeAcademique.objects.order_by('-annee_fin', '-annee_debut').first()
    )
    for motif in MotifPaiement.objects.all():
        updates = []
        if annee and not motif.annee_academique_id:
            motif.annee_academique_id = annee.pk
            updates.append('annee_academique_id')
        code = (motif.code or '').upper()
        nom = (motif.nom or '').upper()
        if 'RATT' in code or 'RATTRAP' in code or 'RATTRAP' in nom:
            motif.contexte = 'session_rattrapage'
        elif (
            'TRANCHE' in code
            or 'TRANCHE' in nom
            or 'SESSION' in nom
            or 'S1' in code
        ):
            motif.contexte = 'session_principale'
        else:
            motif.contexte = 'enrollement'
        updates.append('contexte')
        motif.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('finance', '0003_confirmationpaiement'),
    ]

    operations = [
        migrations.AddField(
            model_name='motifpaiement',
            name='annee_academique',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='motifs_paiement',
                to='academics.anneeacademique',
                verbose_name='Année académique',
            ),
        ),
        migrations.AddField(
            model_name='motifpaiement',
            name='contexte',
            field=models.CharField(
                choices=[
                    ('enrollement', 'Enrôlement'),
                    ('session_principale', 'Session principale'),
                    ('session_rattrapage', 'Session de rattrapage'),
                ],
                default='enrollement',
                max_length=30,
                verbose_name='Contexte',
            ),
        ),
        migrations.RunPython(backfill_annee_contexte, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='motifpaiement',
            name='annee_academique',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='motifs_paiement',
                to='academics.anneeacademique',
                verbose_name='Année académique',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together={('promotion', 'annee_academique', 'contexte', 'code')},
        ),
        migrations.AlterModelOptions(
            name='motifpaiement',
            options={
                'ordering': [
                    'annee_academique__annee_debut',
                    'promotion__filiere',
                    'promotion__ordre',
                    'contexte',
                    'ordre',
                    'nom',
                ],
                'verbose_name': 'Motif de paiement',
                'verbose_name_plural': 'Motifs de paiement',
            },
        ),
    ]
