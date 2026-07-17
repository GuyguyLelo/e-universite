from types import SimpleNamespace

from django.test import TestCase

from evaluations.models import Evaluation


class NoteZeroSaisieTest(TestCase):
    def test_note_champ_post_vide(self):
        from evaluations.views import _note_champ_post_vide

        self.assertTrue(_note_champ_post_vide(''))
        self.assertTrue(_note_champ_post_vide('   '))
        self.assertTrue(_note_champ_post_vide(None))
        self.assertFalse(_note_champ_post_vide('0'))
        self.assertFalse(_note_champ_post_vide('0.0'))
        self.assertFalse(_note_champ_post_vide(' 0 '))


class EvaluationBuildNomTest(TestCase):
    def test_travaux_journaliers(self):
        ec = SimpleNamespace(nom='BDD AVANCEE et NoSQL')
        type_tp = SimpleNamespace(code='TP', nom='Travaux Journaliers')
        self.assertEqual(
            Evaluation.build_nom(type_tp, ec),
            'TJ - BDD AVANCEE et NoSQL',
        )

    def test_examen_session_principale(self):
        ec = SimpleNamespace(nom='BDD AVANCEE et NoSQL')
        type_exam = SimpleNamespace(code='EXAM', nom='Examen')
        session = SimpleNamespace(numero=1)
        self.assertEqual(
            Evaluation.build_nom(type_exam, ec, session),
            'Examen BDD AVANCEE et NoSQL (SP)',
        )

    def test_examen_session_rattrapage(self):
        ec = SimpleNamespace(nom='BDD AVANCEE et NoSQL')
        type_ratt = SimpleNamespace(code='RATT', nom='Rattrapage')
        session = SimpleNamespace(numero=2)
        self.assertEqual(
            Evaluation.build_nom(type_ratt, ec, session),
            'Examen BDD AVANCEE et NoSQL (SR)',
        )
