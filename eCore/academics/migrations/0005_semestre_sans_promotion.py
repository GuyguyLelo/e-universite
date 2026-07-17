from django.db import migrations, models
import django.core.validators


def merge_semestres_par_numero(apps, schema_editor):
    Semestre = apps.get_model('academics', 'Semestre')
    UniteEnseignement = apps.get_model('academics', 'UniteEnseignement')
    Session = apps.get_model('evaluations', 'Session')
    Evaluation = apps.get_model('evaluations', 'Evaluation')
    Note = apps.get_model('evaluations', 'Note')
    Deliberation = apps.get_model('deliberations', 'Deliberation')
    Horaire = apps.get_model('prestation', 'Horaire')

    ElementConstitutif = apps.get_model('academics', 'ElementConstitutif')
    canonical = {}
    for semestre in Semestre.objects.order_by('numero', 'id'):
        keep = canonical.get(semestre.numero)
        if keep is None:
            canonical[semestre.numero] = semestre
            semestre.code = semestre.code or f'S{semestre.numero}'
            semestre.nom = semestre.nom or f'Semestre {semestre.numero}'
            semestre.save(update_fields=['code', 'nom'])
            continue

        for session in Session.objects.filter(semestre_id=semestre.id):
            conflict = Session.objects.filter(semestre_id=keep.id, numero=session.numero).first()
            if conflict:
                for evaluation in Evaluation.objects.filter(session_id=session.id):
                    target_eval = Evaluation.objects.filter(
                        ec_id=evaluation.ec_id,
                        session_id=conflict.id,
                        type_evaluation_id=evaluation.type_evaluation_id,
                    ).first()
                    if target_eval:
                        Note.objects.filter(evaluation_id=evaluation.id).update(evaluation_id=target_eval.id)
                        evaluation.delete()
                    else:
                        evaluation.session_id = conflict.id
                        evaluation.save(update_fields=['session_id'])
                Deliberation.objects.filter(session_id=session.id).delete()
                session.delete()
            else:
                session.semestre_id = keep.id
                session.save(update_fields=['semestre_id'])

        for ue in UniteEnseignement.objects.filter(semestre_id=semestre.id):
            conflict_ue = UniteEnseignement.objects.filter(semestre_id=keep.id, code=ue.code).first()
            if conflict_ue:
                for ec in ElementConstitutif.objects.filter(ue_id=ue.id):
                    conflict_ec = ElementConstitutif.objects.filter(ue_id=conflict_ue.id, code=ec.code).first()
                    if conflict_ec:
                        ec.delete()
                    else:
                        ec.ue_id = conflict_ue.id
                        ec.save(update_fields=['ue_id'])
                ue.delete()
            else:
                ue.semestre_id = keep.id
                ue.save(update_fields=['semestre_id'])

        Horaire.objects.filter(semestre_id=semestre.id).update(semestre_id=keep.id)
        semestre.delete()


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('evaluations', '0001_initial'),
        ('prestation', '0001_initial'),
        ('deliberations', '0002_deliberation_promotion'),
        ('academics', '0004_uniteenseignement_categorie'),
    ]

    operations = [
        migrations.RunPython(merge_semestres_par_numero, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='semestre',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='semestre',
            name='promotion',
        ),
        migrations.AlterField(
            model_name='semestre',
            name='numero',
            field=models.IntegerField(
                unique=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(10),
                ],
                verbose_name='Numéro',
            ),
        ),
        migrations.AlterModelOptions(
            name='semestre',
            options={
                'ordering': ['numero'],
                'verbose_name': 'Semestre',
                'verbose_name_plural': 'Semestres',
            },
        ),
    ]
