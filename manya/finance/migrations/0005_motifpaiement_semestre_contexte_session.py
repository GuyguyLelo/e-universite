# Generated manually

from django.db import migrations, models
import django.db.models.deletion


def renommer_contextes_et_semestre(apps, schema_editor):
    MotifPaiement = apps.get_model('finance', 'MotifPaiement')
    Semestre = apps.get_model('academics', 'Semestre')
    semestres = {s.numero: s.pk for s in Semestre.objects.all()}
    s1 = semestres.get(1)

    for motif in MotifPaiement.objects.all():
        if motif.contexte == 'session_principale':
            motif.contexte = 'enrollement_session_principale'
        elif motif.contexte == 'session_rattrapage':
            motif.contexte = 'enrollement_session_rattrapage'

        if motif.contexte in ('enrollement_session_principale', 'enrollement_session_rattrapage'):
            if not motif.semestre_id:
                code = (motif.code or '').upper()
                nom = (motif.nom or '').upper()
                if 'S2' in code or 'S2' in nom or 'SEM2' in code:
                    motif.semestre_id = semestres.get(2) or s1
                else:
                    motif.semestre_id = s1
        elif motif.contexte == 'enrollement':
            motif.semestre_id = None

        motif.save(update_fields=['contexte', 'semestre_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('finance', '0004_motifpaiement_annee_contexte'),
    ]

    operations = [
        migrations.AddField(
            model_name='motifpaiement',
            name='semestre',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='motifs_paiement',
                to='academics.semestre',
                verbose_name='Semestre',
                help_text='Obligatoire pour les enrôlements de session (S1, S2…). Vide pour l\'enrôlement annuel.',
            ),
        ),
        migrations.AlterField(
            model_name='motifpaiement',
            name='contexte',
            field=models.CharField(
                choices=[
                    ('enrollement', 'Enrôlement'),
                    ('enrollement_session_principale', 'Enrôlement session principale'),
                    ('enrollement_session_rattrapage', 'Enrôlement session rattrapage'),
                ],
                default='enrollement',
                max_length=40,
                verbose_name='Contexte',
            ),
        ),
        migrations.RunPython(renommer_contextes_et_semestre, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together={('promotion', 'annee_academique', 'semestre', 'contexte', 'code')},
        ),
        migrations.AlterModelOptions(
            name='motifpaiement',
            options={
                'ordering': [
                    'annee_academique__annee_debut',
                    'promotion__filiere',
                    'promotion__ordre',
                    'semestre__numero',
                    'contexte',
                    'ordre',
                    'nom',
                ],
                'verbose_name': 'Motif de paiement',
                'verbose_name_plural': 'Motifs de paiement',
            },
        ),
    ]
