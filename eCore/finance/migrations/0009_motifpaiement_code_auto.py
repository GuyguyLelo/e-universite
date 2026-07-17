from collections import defaultdict

from django.db import migrations, models


def fusionner_et_normaliser_codes(apps, schema_editor):
    MotifPaiement = apps.get_model('finance', 'MotifPaiement')
    ConfirmationPaiement = apps.get_model('finance', 'ConfirmationPaiement')
    Semestre = apps.get_model('academics', 'Semestre')
    suffixes = {
        'enrollement_session_principale': 'PRINC',
        'enrollement_session_rattrapage': 'RATT',
    }

    groupes = defaultdict(list)
    for motif in MotifPaiement.objects.all().order_by('id'):
        cle = (motif.annee_academique_id, motif.semestre_id, motif.contexte)
        groupes[cle].append(motif.pk)

    for (_annee_id, semestre_id, contexte), ids in groupes.items():
        garder_id = ids[0]
        semestre = Semestre.objects.filter(pk=semestre_id).first()
        suffix = suffixes.get(contexte, 'MOTIF')
        code = f'{semestre.code}-{suffix}'[:20] if semestre else suffix

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

        MotifPaiement.objects.filter(pk=garder_id).update(code=code)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('finance', '0008_motifpaiement_devise'),
    ]

    operations = [
        migrations.RunPython(fusionner_et_normaliser_codes, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='motifpaiement',
            unique_together={('annee_academique', 'semestre', 'contexte')},
        ),
        migrations.AlterField(
            model_name='motifpaiement',
            name='code',
            field=models.CharField(editable=False, max_length=20, verbose_name='Code'),
        ),
    ]
