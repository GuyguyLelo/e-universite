from collections import defaultdict

from django.db import migrations


def fusionner_motifs_sans_promotion(apps, schema_editor):
    MotifPaiement = apps.get_model('finance', 'MotifPaiement')
    ConfirmationPaiement = apps.get_model('finance', 'ConfirmationPaiement')

    groupes = defaultdict(list)
    for motif in MotifPaiement.objects.all().order_by('id'):
        cle = (
            motif.annee_academique_id,
            motif.semestre_id,
            motif.contexte,
            motif.code,
        )
        groupes[cle].append(motif.pk)

    for _cle, ids in groupes.items():
        garder_id = ids[0]
        for dup_id in ids[1:]:
            for conf in ConfirmationPaiement.objects.filter(motif_paiement_id=dup_id):
                existante = ConfirmationPaiement.objects.filter(
                    inscription_id=conf.inscription_id,
                    motif_paiement_id=garder_id,
                ).first()
                if existante:
                    if conf.confirme and not existante.confirme:
                        existante.confirme = True
                        existante.save(update_fields=['confirme'])
                    conf.delete()
                else:
                    conf.motif_paiement_id = garder_id
                    conf.save(update_fields=['motif_paiement_id'])
            MotifPaiement.objects.filter(pk=dup_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_supprimer_enrollement_annuel'),
    ]

    operations = [
        migrations.RunPython(fusionner_motifs_sans_promotion, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='motifpaiement',
            name='promotion',
        ),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together={('annee_academique', 'semestre', 'contexte', 'code')},
        ),
        migrations.AlterModelOptions(
            name='motifpaiement',
            options={
                'ordering': [
                    'annee_academique__annee_debut',
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
