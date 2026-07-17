from datetime import date

from django.db import migrations, models
import django.db.models.deletion


def _annee_par_defaut(AnneeAcademique):
    return (
        AnneeAcademique.objects.filter(active=True).order_by('-annee_debut').first()
        or AnneeAcademique.objects.order_by('-annee_debut').first()
    )


def _annee_ou_creer(AnneeAcademique):
    annee = _annee_par_defaut(AnneeAcademique)
    if annee:
        return annee
    return AnneeAcademique.objects.create(
        code='MIG-DEFAULT',
        annee_debut=2000,
        annee_fin=2001,
        date_debut=date(2000, 9, 1),
        date_fin=date(2001, 8, 31),
        active=True,
    )


def peupler_annee_session(apps, schema_editor):
    Session = apps.get_model('evaluations', 'Session')
    AnneeAcademique = apps.get_model('academics', 'AnneeAcademique')
    annee = _annee_ou_creer(AnneeAcademique)
    Session.objects.filter(annee_academique__isnull=True).update(annee_academique_id=annee.pk)


def peupler_annee_evaluation(apps, schema_editor):
    Evaluation = apps.get_model('evaluations', 'Evaluation')
    Session = apps.get_model('evaluations', 'Session')
    for evaluation in Evaluation.objects.filter(annee_academique__isnull=True).iterator():
        annee_id = (
            Session.objects.filter(pk=evaluation.session_id)
            .values_list('annee_academique_id', flat=True)
            .first()
        )
        if annee_id:
            Evaluation.objects.filter(pk=evaluation.pk).update(annee_academique_id=annee_id)


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
        ('evaluations', '0003_increase_session_code_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='annee_academique',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='sessions_evaluation',
                to='academics.anneeacademique',
                verbose_name='Année académique',
            ),
        ),
        migrations.RunPython(peupler_annee_session, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='session',
            name='annee_academique',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='sessions_evaluation',
                to='academics.anneeacademique',
                verbose_name='Année académique',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='session',
            unique_together={('semestre', 'numero', 'annee_academique')},
        ),
        migrations.AddField(
            model_name='evaluation',
            name='annee_academique',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='evaluations',
                to='academics.anneeacademique',
                verbose_name='Année académique',
            ),
        ),
        migrations.RunPython(peupler_annee_evaluation, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='evaluation',
            name='annee_academique',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='evaluations',
                to='academics.anneeacademique',
                verbose_name='Année académique',
            ),
        ),
    ]
