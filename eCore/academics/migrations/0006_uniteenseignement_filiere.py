from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0005_semestre_sans_promotion'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='uniteenseignement',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='uniteenseignement',
            name='filiere',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ues',
                to='academics.filiere',
                verbose_name='Filière',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='uniteenseignement',
            unique_together={('semestre', 'filiere', 'code')},
        ),
        migrations.AlterModelOptions(
            name='uniteenseignement',
            options={
                'ordering': ['semestre', 'filiere', 'ordre', 'code'],
                'verbose_name': "Unité d'Enseignement",
                'verbose_name_plural': "Unités d'Enseignement",
            },
        ),
    ]
