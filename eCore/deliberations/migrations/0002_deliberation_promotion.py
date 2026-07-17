from django.db import migrations, models
import django.db.models.deletion


def populate_deliberation_promotion(apps, schema_editor):
    Deliberation = apps.get_model('deliberations', 'Deliberation')
    Session = apps.get_model('evaluations', 'Session')
    Semestre = apps.get_model('academics', 'Semestre')
    Promotion = apps.get_model('academics', 'Promotion')

    default_promotion = Promotion.objects.order_by('id').first()
    for deliberation in Deliberation.objects.all():
        session = Session.objects.filter(pk=deliberation.session_id).first()
        if not session:
            continue
        semestre = Semestre.objects.filter(pk=session.semestre_id).first()
        promotion_id = getattr(semestre, 'promotion_id', None) if semestre else None
        if not promotion_id and default_promotion:
            promotion_id = default_promotion.pk
        if promotion_id:
            deliberation.promotion_id = promotion_id
            deliberation.save(update_fields=['promotion_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0004_uniteenseignement_categorie'),
        ('deliberations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliberation',
            name='promotion',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='deliberations',
                to='academics.promotion',
                verbose_name='Promotion',
            ),
        ),
        migrations.RunPython(populate_deliberation_promotion, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='deliberation',
            name='promotion',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='deliberations',
                to='academics.promotion',
                verbose_name='Promotion',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='deliberation',
            unique_together={('session', 'promotion')},
        ),
    ]
