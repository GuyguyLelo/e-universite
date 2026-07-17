"""
Données test — notes pour tous les EC/UE RX (Semestre 7), tous les étudiants inscrits.

Usage:
  python manage.py seed_notes_rx_s7
  python manage.py seed_notes_rx_s7 --clear
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AnneeAcademique, ElementConstitutif, Filiere, Semestre, UniteEnseignement
from deliberations.services import DeliberationEngine
from evaluations.models import Evaluation, Note, NoteEC, NoteUE, Session, TypeEvaluation
from students.models import Inscription, Student


def _note_test(etudiant_id: int, evaluation_id: int) -> tuple[Decimal | None, bool, bool]:
    """Note déterministe entre 8.5 et 17.5 ; ~6 % d'absences."""
    digest = hashlib.md5(f'{etudiant_id}:{evaluation_id}'.encode()).hexdigest()
    bucket = int(digest[:8], 16)
    absent = (bucket % 100) < 6
    if absent:
        justifie = (bucket % 2) == 0
        return None, True, justifie
    value = Decimal('8.5') + Decimal(bucket % 901) / Decimal('100')
    return value.quantize(Decimal('0.01')), False, False


class Command(BaseCommand):
    help = 'Génère des notes test pour tous les EC/UE RX (S7) et tous les étudiants RX inscrits.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprime les notes / évaluations RX S7 existantes avant import',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        annee = AnneeAcademique.get_active()
        if not annee:
            self.stderr.write(self.style.ERROR('Aucune année académique active.'))
            return

        filiere = Filiere.objects.filter(code='RX').first()
        if not filiere:
            self.stderr.write(self.style.ERROR('Filière RX introuvable.'))
            return

        semestre = Semestre.objects.filter(code='S7').first()
        if not semestre:
            self.stderr.write(self.style.ERROR('Semestre S7 introuvable. Lancez import_maquette_rx_s7.'))
            return

        inscriptions = (
            Inscription.objects.filter(
                annee_academique=annee,
                classe__promotion__filiere=filiere,
            )
            .eligibles_listes()
            .select_related('etudiant', 'classe__promotion')
        )
        etudiants = list({ins.etudiant for ins in inscriptions})
        if not etudiants:
            self.stderr.write(self.style.ERROR('Aucun étudiant RX inscrit sur l\'année active.'))
            return

        ecs = ElementConstitutif.objects.filter(
            ue__semestre=semestre,
            ue__filiere=filiere,
            active=True,
        ).select_related('ue')
        ues = UniteEnseignement.objects.filter(
            semestre=semestre,
            filiere=filiere,
            active=True,
        )
        if not ecs.exists():
            self.stderr.write(self.style.ERROR('Aucun EC RX S7. Lancez import_maquette_rx_s7.'))
            return

        session = self._get_or_create_session(semestre, annee)
        types_eval = self._get_types_evaluation()
        type_tj = types_eval['TP']
        type_exam = types_eval['EXAM']
        saisie_par = User.objects.filter(is_superuser=True).first()

        if options['clear']:
            eval_ids = list(
                Evaluation.objects.filter(ec__in=ecs, session=session).values_list('pk', flat=True)
            )
            deleted_notes, _ = Note.objects.filter(evaluation_id__in=eval_ids).delete()
            deleted_eval, _ = Evaluation.objects.filter(pk__in=eval_ids).delete()
            deleted_ec, _ = NoteEC.objects.filter(
                etudiant__in=etudiants,
                ec__in=ecs,
                session=session,
            ).delete()
            deleted_ue, _ = NoteUE.objects.filter(
                etudiant__in=etudiants,
                ue__in=ues,
                session=session,
            ).delete()
            self.stdout.write(self.style.WARNING(
                f'Nettoyage : {deleted_notes} notes, {deleted_eval} évaluations, '
                f'{deleted_ec} notes EC, {deleted_ue} notes UE.'
            ))

        evaluations = []
        for ec in ecs:
            for type_eval in (type_tj, type_exam):
                evaluation, _ = Evaluation.objects.update_or_create(
                    ec=ec,
                    session=session,
                    type_evaluation=type_eval,
                    defaults={
                        'annee_academique': session.annee_academique,
                        'code': Evaluation.build_code(ec, session, type_eval),
                        'nom': Evaluation.build_nom(type_eval, ec, session),
                        'date_evaluation': session.date_debut + timedelta(days=ec.ordre),
                        'coefficient': type_eval.coefficient,
                        'note_max': type_eval.note_max,
                        'active': True,
                    },
                )
                evaluations.append(evaluation)

        notes_created = 0
        notes_updated = 0
        for evaluation in evaluations:
            for etudiant in etudiants:
                note_value, absent, justifie = _note_test(etudiant.pk, evaluation.pk)
                note_obj, created = Note.objects.update_or_create(
                    etudiant=etudiant,
                    evaluation=evaluation,
                    defaults={
                        'note': note_value,
                        'note_sur': evaluation.note_max,
                        'absent': absent,
                        'justifie': justifie,
                        'saisie_par': saisie_par,
                    },
                )
                if created:
                    notes_created += 1
                else:
                    notes_updated += 1

        promotion = inscriptions.first().classe.promotion
        engine = DeliberationEngine(session, promotion)
        notes_ec_count = 0
        notes_ue_count = 0

        for ec in ecs:
            for etudiant in etudiants:
                note_ec = engine.calculer_note_ec(etudiant, ec)
                valide = bool(note_ec and engine.valider_ec(etudiant, ec, note_ec))
                credits = ec.credits_ects if valide else Decimal('0.00')
                NoteEC.objects.update_or_create(
                    etudiant=etudiant,
                    ec=ec,
                    session=session,
                    defaults={
                        'note_finale': note_ec,
                        'credits_obtenus': credits,
                        'valide': valide,
                        'capitalise': valide and ec.capitalisable,
                        'calculee_auto': True,
                    },
                )
                notes_ec_count += 1

        for ue in ues:
            for etudiant in etudiants:
                note_ue = engine.calculer_note_ue(etudiant, ue)
                valide = bool(note_ue and engine.valider_ue(etudiant, ue, note_ue))
                credits = ue.credits_ects if valide else Decimal('0.00')
                NoteUE.objects.update_or_create(
                    etudiant=etudiant,
                    ue=ue,
                    session=session,
                    defaults={
                        'note_finale': note_ue,
                        'credits_obtenus': credits,
                        'valide': valide,
                        'capitalise': valide and ue.capitalisable,
                        'calculee_auto': True,
                    },
                )
                notes_ue_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Notes test RX S7 : {len(etudiants)} étudiant(s), {ecs.count()} EC, '
            f'{ues.count()} UE, {len(evaluations)} évaluation(s).'
        ))
        self.stdout.write(
            f'  - {notes_created} notes creees, {notes_updated} mises a jour ; '
            f'{notes_ec_count} notes EC, {notes_ue_count} notes UE.'
        )

    def _get_or_create_session(self, semestre, annee):
        date_debut = annee.date_debut
        date_fin = min(annee.date_fin, date_debut + timedelta(days=120))
        session, created = Session.objects.get_or_create(
            semestre=semestre,
            numero=1,
            annee_academique=annee,
            defaults={
                'code': f'{semestre.code}-S1',
                'nom': f'Session 1 - {semestre.nom}',
                'date_debut': date_debut,
                'date_fin': date_fin,
                'date_deliberation': date_fin + timedelta(days=7),
                'deliberation_faite': False,
                'verrouillee': False,
                'active': True,
            },
        )
        if created:
            self.stdout.write(f'Session créée : {session.code}')
        return session

    def _get_types_evaluation(self):
        specs = {
            'TP': ('Travaux Journaliers', Decimal('1.00'), 1),
            'EXAM': ('Examen du semestre', Decimal('1.00'), 2),
        }
        result = {}
        for code, (nom, coef, ordre) in specs.items():
            type_eval, _ = TypeEvaluation.objects.get_or_create(
                code=code,
                defaults={
                    'nom': nom,
                    'coefficient': coef,
                    'note_max': Decimal('10.00'),
                    'ordre': ordre,
                    'active': True,
                },
            )
            result[code] = type_eval
        return result
