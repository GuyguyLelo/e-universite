from django.db import migrations, models
import django.db.models.deletion


def convertir_motifs_annuels(apps, schema_editor):
    MotifPaiement = apps.get_model('finance', 'MotifPaiement')
    Semestre = apps.get_model('academics', 'Semestre')
    s1 = Semestre.objects.order_by('numero').first()

    for motif in MotifPaiement.objects.filter(contexte='enrollement'):
        motif.contexte = 'enrollement_session_principale'
        if not motif.semestre_id and s1:
            motif.semestre_id = s1.pk
        motif.save(update_fields=['contexte', 'semestre_id'])

    for motif in MotifPaiement.objects.filter(semestre__isnull=True):
        if s1:
            motif.semestre_id = s1.pk
            motif.save(update_fields=['semestre_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('finance', '0005_motifpaiement_semestre_contexte_session'),
    ]

    operations = [
        migrations.RunPython(convertir_motifs_annuels, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='motifpaiement',
            name='contexte',
            field=models.CharField(
                choices=[
                    ('enrollement_session_principale', 'Enrôlement session principale'),
                    ('enrollement_session_rattrapage', 'Enrôlement session rattrapage'),
                ],
                default='enrollement_session_principale',
                max_length=40,
                verbose_name='Contexte',
            ),
        ),
        migrations.AlterField(
            model_name='motifpaiement',
            name='semestre',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='motifs_paiement',
                to='academics.semestre',
                verbose_name='Semestre',
            ),
        ),
    ]
