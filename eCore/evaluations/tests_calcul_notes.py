from decimal import Decimal

from django.test import TestCase

from evaluations.calcul_notes import (
    BAREME_TJ_EXAM,
    calculer_note_ec,
    calculer_note_ec_combine_sessions,
    est_type_exam,
    est_type_tj,
    etudiant_convoque_rattrapage,
    note_exam_retenue_sur_10,
    plafond_note_saisie,
    valider_note_saisie,
)


class TypeEvaluationCodesTest(TestCase):
    def test_tj_inclut_cc_historique(self):
        class Fake:
            code = 'CC'

        self.assertTrue(est_type_tj(Fake()))

    def test_exam_codes(self):
        class Fake:
            code = 'EXAM'

        self.assertTrue(est_type_exam(Fake()))


class CalculNoteECTest(TestCase):
    def test_moyenne_tj_et_examen_sur_10_ramenee_sur_20(self):
        import evaluations.calcul_notes as mod

        class FakeType:
            def __init__(self, code):
                self.code = code

        class FakeEval:
            def __init__(self, code):
                self.type_evaluation = FakeType(code)
                self.coefficient = Decimal('1.00')
                self.note_max = BAREME_TJ_EXAM

        class FakeNote:
            def __init__(self, note):
                self.absent = False
                self.justifie = False
                self.note = Decimal(str(note))
                self.note_sur = BAREME_TJ_EXAM

            @property
            def note_finale(self):
                return (self.note / self.note_sur) * Decimal('20.00')

        notes_db = {}

        class FakeNoteManager:
            @staticmethod
            def get(etudiant, evaluation):
                return notes_db[evaluation.type_evaluation.code]

        original = mod.Note
        mod.Note = type('Note', (), {'objects': FakeNoteManager, 'DoesNotExist': Exception})
        try:
            notes_db['TJ'] = FakeNote(6)
            notes_db['EXAM'] = FakeNote(8)
            result = calculer_note_ec(
                object(),
                [FakeEval('TJ'), FakeEval('EXAM')],
            )
            self.assertEqual(result, Decimal('14.00'))
        finally:
            mod.Note = original

    def test_plusieurs_tj_moyennes_avant_examen(self):
        import evaluations.calcul_notes as mod

        class FakeType:
            def __init__(self, code):
                self.code = code

        class FakeEval:
            def __init__(self, code):
                self.type_evaluation = FakeType(code)
                self.coefficient = Decimal('1.00')
                self.note_max = BAREME_TJ_EXAM

        class FakeNote:
            def __init__(self, note):
                self.absent = False
                self.justifie = False
                self.note = Decimal(str(note))
                self.note_sur = BAREME_TJ_EXAM

            @property
            def note_finale(self):
                return (self.note / self.note_sur) * Decimal('20.00')

        notes_db = {}

        class FakeNoteManager:
            @staticmethod
            def get(etudiant, evaluation):
                key = id(evaluation)
                if key not in notes_db:
                    raise Exception('DoesNotExist')
                return notes_db[key]

        original = mod.Note
        mod.Note = type('Note', (), {'objects': FakeNoteManager, 'DoesNotExist': Exception})
        try:
            etudiant = object()
            ev_tj1 = FakeEval('TJ')
            ev_tj2 = FakeEval('TJ')
            ev_exam = FakeEval('EXAM')
            notes_db[id(ev_tj1)] = FakeNote(5)
            notes_db[id(ev_tj2)] = FakeNote(7)
            notes_db[id(ev_exam)] = FakeNote(8)
            result = calculer_note_ec(etudiant, [ev_tj1, ev_tj2, ev_exam])
            # moy TJ = 6/10, exam = 8/10 → 7/10 → 14/20
            self.assertEqual(result, Decimal('14.00'))
        finally:
            mod.Note = original

    def test_ancien_bareme_sur_20_normalise_sur_10(self):
        import evaluations.calcul_notes as mod

        class FakeType:
            code = 'TJ'

        class FakeEval:
            type_evaluation = FakeType()
            coefficient = Decimal('1.00')
            note_max = Decimal('20.00')

        class FakeNote:
            absent = False
            justifie = False
            note = Decimal('12.00')
            note_sur = Decimal('20.00')

            @property
            def note_finale(self):
                return self.note

        class FakeNoteManager:
            @staticmethod
            def get(*args, **kwargs):
                return FakeNote()

        original = mod.Note
        mod.Note = type(
            'Note',
            (),
            {
                'objects': FakeNoteManager,
                'DoesNotExist': Exception,
            },
        )
        try:
            result = calculer_note_ec(object(), [FakeEval()])
            self.assertIsNone(result)
        finally:
            mod.Note = original

    def test_moyenne_none_si_note_manquante(self):
        import evaluations.calcul_notes as mod

        class FakeType:
            def __init__(self, code):
                self.code = code

        class FakeEval:
            def __init__(self, code):
                self.type_evaluation = FakeType(code)
                self.coefficient = Decimal('1.00')
                self.note_max = BAREME_TJ_EXAM

        class FakeNote:
            def __init__(self, note):
                self.absent = False
                self.justifie = False
                self.note = Decimal(str(note))
                self.note_sur = BAREME_TJ_EXAM

            @property
            def note_finale(self):
                return (self.note / self.note_sur) * Decimal('20.00')

        notes_db = {}

        class FakeNoteManager:
            @staticmethod
            def get(etudiant, evaluation):
                key = evaluation.type_evaluation.code
                if key not in notes_db:
                    raise Exception('DoesNotExist')
                return notes_db[key]

        original = mod.Note
        mod.Note = type('Note', (), {'objects': FakeNoteManager, 'DoesNotExist': Exception})
        try:
            notes_db['TJ'] = FakeNote(8)
            result = calculer_note_ec(object(), [FakeEval('TJ'), FakeEval('EXAM')])
            self.assertIsNone(result)
        finally:
            mod.Note = original


class RattrapageCommeExamenTest(TestCase):
    def test_convoque_si_examen_inferieur_a_10(self):
        self.assertTrue(etudiant_convoque_rattrapage(Decimal('9.50')))
        self.assertFalse(etudiant_convoque_rattrapage(Decimal('10.00')))
        self.assertFalse(etudiant_convoque_rattrapage(Decimal('10.50')))
        self.assertFalse(etudiant_convoque_rattrapage(None))

    def test_examen_retenu_ou_rattrapage(self):
        self.assertEqual(
            note_exam_retenue_sur_10(Decimal('11.00'), Decimal('8.00')),
            Decimal('11.00'),
        )
        self.assertEqual(
            note_exam_retenue_sur_10(Decimal('7.00'), Decimal('9.00')),
            Decimal('9.00'),
        )

    def test_combine_tj_exam_rattrapage(self):
        import evaluations.calcul_notes as mod

        class FakeType:
            def __init__(self, code):
                self.code = code

        class FakeEval:
            def __init__(self, code):
                self.type_evaluation = FakeType(code)
                self.coefficient = Decimal('1.00')
                self.note_max = BAREME_TJ_EXAM

        class FakeNote:
            def __init__(self, note):
                self.absent = False
                self.justifie = False
                self.note = Decimal(str(note))
                self.note_sur = BAREME_TJ_EXAM

            @property
            def note_finale(self):
                return (self.note / self.note_sur) * Decimal('20.00')

        notes_db = {}

        class FakeNoteManager:
            @staticmethod
            def get(etudiant, evaluation):
                return notes_db[id(evaluation)]

        original = mod.Note
        mod.Note = type('Note', (), {'objects': FakeNoteManager, 'DoesNotExist': Exception})
        try:
            ev_tj = FakeEval('TJ')
            ev_exam = FakeEval('EXAM')
            ev_ratt = FakeEval('RATT')
            notes_db[id(ev_tj)] = FakeNote(8)
            notes_db[id(ev_exam)] = FakeNote(6)
            notes_db[id(ev_ratt)] = FakeNote(9)
            result = calculer_note_ec_combine_sessions(
                object(),
                [ev_tj, ev_exam],
                [ev_ratt],
            )
            self.assertEqual(result, Decimal('17.00'))
        finally:
            mod.Note = original

    def test_resume_cotation_ec(self):
        import evaluations.calcul_notes as mod
        from evaluations.calcul_notes import resume_cotation_ec_etudiant

        class FakeType:
            def __init__(self, code):
                self.code = code

        class FakeEval:
            def __init__(self, code):
                self.type_evaluation = FakeType(code)
                self.coefficient = Decimal('1.00')
                self.note_max = BAREME_TJ_EXAM

        class FakeNote:
            def __init__(self, note):
                self.absent = False
                self.justifie = False
                self.note = Decimal(str(note))
                self.note_sur = BAREME_TJ_EXAM

            @property
            def note_finale(self):
                return (self.note / self.note_sur) * Decimal('20.00')

        notes_db = {}

        class FakeNoteManager:
            @staticmethod
            def get(etudiant, evaluation):
                return notes_db[id(evaluation)]

        original = mod.Note
        mod.Note = type('Note', (), {'objects': FakeNoteManager, 'DoesNotExist': Exception})
        try:
            ev_tj = FakeEval('TJ')
            ev_exam = FakeEval('EXAM')
            notes_db[id(ev_tj)] = FakeNote(8)
            notes_db[id(ev_exam)] = FakeNote(6)
            resume = resume_cotation_ec_etudiant(object(), [ev_tj, ev_exam])
            self.assertEqual(resume['tj_sur_10'], Decimal('8.00'))
            self.assertEqual(resume['exam_sur_10'], Decimal('6.00'))
            self.assertEqual(resume['moy_sur_20'], Decimal('14.00'))

            resume_incomplete = resume_cotation_ec_etudiant(object(), [ev_tj])
            self.assertEqual(resume_incomplete['tj_sur_10'], Decimal('8.00'))
            self.assertIsNone(resume_incomplete['exam_sur_10'])
            self.assertIsNone(resume_incomplete['moy_sur_20'])
        finally:
            mod.Note = original


class PlafondNoteSaisieTest(TestCase):
    def _fake_eval(self, code, note_max=Decimal('20.00')):
        class FakeType:
            def __init__(self, c):
                self.code = c

        class FakeEval:
            def __init__(self, c, nm):
                self.type_evaluation = FakeType(c)
                self.note_max = nm

        return FakeEval(code, note_max)

    def test_tj_exam_rattr_plafond_10(self):
        for code in ('TJ', 'EXAM', 'RATT'):
            with self.subTest(code=code):
                self.assertEqual(plafond_note_saisie(self._fake_eval(code)), BAREME_TJ_EXAM)

    def test_valider_note_accepte_jusqua_10(self):
        valider_note_saisie(Decimal('10'), self._fake_eval('TJ'))
        valider_note_saisie(Decimal('0'), self._fake_eval('EXAM'))

    def test_valider_note_refuse_sup_10(self):
        with self.assertRaises(ValueError) as ctx:
            valider_note_saisie(Decimal('10.5'), self._fake_eval('TJ'))
        self.assertIn('inférieure ou égale à 10', str(ctx.exception))

    def test_valider_note_refuse_negative(self):
        with self.assertRaises(ValueError):
            valider_note_saisie(Decimal('-1'), self._fake_eval('EXAM'))

