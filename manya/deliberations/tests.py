from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase

from academics.models import ElementConstitutif
from deliberations.access import (
    user_can_access_deliberation,
    user_can_manage_deliberations,
)
from deliberations.decision_services import (
    analyser_validation_ues,
    ecs_notes_eliminatoires,
    produire_decision_agregee,
    produire_decision_semestre,
)
from deliberations.services import DeliberationEngine
from deliberations.cycle_services import (
    DeliberationCycleMasterEngine,
    peut_deliberer_cycle_master,
)
from deliberations.dettes_services import (
    SEUIL_VALIDATION_EC,
    ecs_en_dette_etudiant,
    promotion_precedente,
    semestres_pour_promotion,
)


class DettesAcademiquesTest(SimpleTestCase):
    def test_ec_note_inferieure_10_est_dette(self):
        ec = SimpleNamespace(
            pk=1, code='EC1', nom='Cours A', ordre=1,
            ue=SimpleNamespace(pk=1, code='UE1', ordre=1),
            credits_ects=Decimal('3'),
        )
        engine = MagicMock()
        engine._ecs_semestre_qs.return_value = [ec]
        engine._note_ec_effective.return_value = Decimal('8.50')

        dettes = ecs_en_dette_etudiant(engine, SimpleNamespace(pk=1))
        self.assertEqual(len(dettes), 1)
        self.assertEqual(dettes[0]['note'], Decimal('8.50'))

    def test_ec_note_10_ou_plus_n_est_pas_dette(self):
        ec = SimpleNamespace(
            pk=1, code='EC1', nom='Cours A', ordre=1,
            ue=SimpleNamespace(pk=1, code='UE1', ordre=1),
            credits_ects=Decimal('3'),
        )
        engine = MagicMock()
        engine._ecs_semestre_qs.return_value = [ec]
        engine._note_ec_effective.return_value = Decimal('10.00')

        self.assertEqual(ecs_en_dette_etudiant(engine, SimpleNamespace(pk=1)), [])

    def test_seuil_validation_est_10(self):
        self.assertEqual(SEUIL_VALIDATION_EC, Decimal('10.00'))

    @patch('deliberations.dettes_services.Semestre')
    def test_semestres_pour_promotion_ordre_2(self, semestre_model):
        promo = SimpleNamespace(ordre=2)
        semestre_model.objects.filter.return_value.order_by.return_value = ['S3', 'S4']
        semestres_pour_promotion(promo)
        semestre_model.objects.filter.assert_called_once_with(numero__in=(3, 4), active=True)

    def test_promotion_precedente_ordre_1_retourne_none(self):
        self.assertIsNone(promotion_precedente(SimpleNamespace(ordre=1, filiere_id=1)))


User = get_user_model()


class JuryAccessTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin_jury', password='x')
        self.admin.is_superuser = True
        self.admin.save()
        self.jury_user = User.objects.create_user('membre_jury', password='x')
        perm = Permission.objects.get(codename='view_deliberation', content_type__app_label='deliberations')
        self.jury_user.user_permissions.add(perm)
        self.autre = User.objects.create_user('autre', password='x')
        self.deliberation = MagicMock()
        self.deliberation.president_jury_id = self.jury_user.pk
        self.deliberation.membres_jury.filter.return_value.exists.return_value = False

    def test_gestionnaire_voit_toutes_les_deliberations(self):
        self.assertTrue(user_can_manage_deliberations(self.admin))

    def test_membre_president_accede_a_sa_deliberation(self):
        self.assertTrue(user_can_access_deliberation(self.jury_user, self.deliberation))

    def test_utilisateur_non_membre_refuse(self):
        self.assertFalse(user_can_access_deliberation(self.autre, self.deliberation))


class SeuilValidationTest(SimpleTestCase):
    def _engine(self):
        engine = DeliberationEngine.__new__(DeliberationEngine)
        engine.parametres = SimpleNamespace(
            seuil_validation=Decimal('10.00'),
            seuil_credits_minimum=30,
            passage_avec_dettes=True,
        )
        engine._note_depasse_seuil = DeliberationEngine._note_depasse_seuil.__get__(engine)
        engine.session = SimpleNamespace()
        engine.session_principale = None
        engine.mode_final = False
        engine.filiere_id = None
        return engine

    def test_note_10_est_validee(self):
        engine = DeliberationEngine.__new__(DeliberationEngine)
        seuil = Decimal('10.00')
        self.assertTrue(engine._note_depasse_seuil(Decimal('10.00'), seuil))
        self.assertTrue(engine._note_depasse_seuil(Decimal('10.01'), seuil))
        self.assertFalse(engine._note_depasse_seuil(Decimal('9.99'), seuil))
        self.assertFalse(engine._note_depasse_seuil(None, seuil))

    def test_note_eliminatoire_bloque_validation_ec(self):
        engine = DeliberationEngine.__new__(DeliberationEngine)
        engine.parametres = SimpleNamespace(
            seuil_validation=Decimal('10.00'),
            compensation_intra_ue=True,
        )
        engine._note_depasse_seuil = DeliberationEngine._note_depasse_seuil.__get__(engine)
        ec = ElementConstitutif(
            note_eliminatoire=Decimal('7.00'),
            seuil_validation=Decimal('10.00'),
            compensation_autorisee=True,
        )
        self.assertFalse(engine.valider_ec(None, ec, Decimal('6.50')))

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_moyenne_inferieure_au_seuil_produit_ajourne(self, _mock_def):
        engine = self._engine()
        resultat = {
            'moyenne_semestre': Decimal('9.50'),
            'credits_obtenus': Decimal('30.00'),
            'credits_totaux': Decimal('30.00'),
            'notes_ue': {},
        }
        self.assertEqual(produire_decision_semestre(engine, None, resultat), 'ajourne')

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_moyenne_10_toutes_ue_directes_produit_admis(self, _mock_def):
        engine = self._engine()
        resultat = {
            'moyenne_semestre': Decimal('10.00'),
            'credits_obtenus': Decimal('30.00'),
            'credits_totaux': Decimal('30.00'),
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('10.00'), 'valide': True},
            },
        }
        self.assertEqual(produire_decision_semestre(engine, None, resultat), 'admis')

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_ue_compensee_produit_admis_compensation(self, _mock_def):
        engine = self._engine()
        resultat = {
            'moyenne_semestre': Decimal('11.00'),
            'credits_obtenus': Decimal('30.00'),
            'credits_totaux': Decimal('30.00'),
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('12.00'), 'valide': True},
                2: {'ue': SimpleNamespace(), 'note': Decimal('9.00'), 'valide': True},
            },
        }
        self.assertEqual(produire_decision_semestre(engine, None, resultat), 'admis_compensation')

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_note_eliminatoire_ec_produit_admis_compensation(self, _mock_def):
        engine = self._engine()
        ec = SimpleNamespace(note_eliminatoire=Decimal('7.00'))
        resultat = {
            'moyenne_semestre': Decimal('12.00'),
            'credits_obtenus': Decimal('30.00'),
            'credits_totaux': Decimal('30.00'),
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('12.00'), 'valide': True},
            },
            'notes_ec': {
                1: {'ec': ec, 'note': Decimal('6.00'), 'valide': False, 'est_eliminatoire': True},
            },
        }
        self.assertEqual(produire_decision_semestre(engine, None, resultat), 'admis_compensation')
        self.assertEqual(len(ecs_notes_eliminatoires(resultat)), 1)

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_ue_non_validee_avec_passage_dettes(self, _mock_def):
        engine = self._engine()
        resultat = {
            'moyenne_semestre': Decimal('10.00'),
            'credits_obtenus': Decimal('30.00'),
            'credits_totaux': Decimal('60.00'),
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('12.00'), 'valide': True},
                2: {'ue': SimpleNamespace(), 'note': Decimal('8.00'), 'valide': False},
            },
        }
        self.assertEqual(produire_decision_semestre(engine, None, resultat), 'admis_avec_dettes')

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=True)
    def test_absence_non_justifiee_produit_defaillant(self, _mock_def):
        engine = self._engine()
        resultat = {
            'moyenne_semestre': Decimal('12.00'),
            'credits_obtenus': Decimal('30.00'),
            'credits_totaux': Decimal('30.00'),
            'notes_ue': {},
        }
        self.assertEqual(produire_decision_semestre(engine, None, resultat), 'defaillant')


class DecisionAgregeeTest(SimpleTestCase):
    def _engine(self):
        engine = SimpleNamespace()
        engine.parametres = SimpleNamespace(
            seuil_validation=Decimal('10.00'),
            seuil_credits_minimum=30,
            passage_avec_dettes=True,
        )
        engine._note_depasse_seuil = lambda m, s: m is not None and m >= s
        engine.session = SimpleNamespace()
        engine.session_principale = None
        engine.mode_final = False
        engine.filiere_id = None
        return engine

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_agregee_admis_sans_compensation(self, _mock_def):
        engine = self._engine()
        resultat = {
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('12.00'), 'valide': True},
            },
        }
        decision = produire_decision_agregee(
            [engine], None, [resultat], Decimal('12.00'),
            Decimal('60.00'), Decimal('60.00'), 2,
        )
        self.assertEqual(decision, 'admis')

    @patch('deliberations.decision_services.etudiant_defaillant', return_value=False)
    def test_agregee_avec_dettes(self, _mock_def):
        engine = self._engine()
        resultat = {
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('12.00'), 'valide': True},
                2: {'ue': SimpleNamespace(), 'note': Decimal('8.00'), 'valide': False},
            },
        }
        decision = produire_decision_agregee(
            [engine], None, [resultat], Decimal('11.00'),
            Decimal('125.00'), Decimal('150.00'), 4,
        )
        self.assertEqual(decision, 'admis_avec_dettes')


class CycleMasterDeliberationTest(SimpleTestCase):
    def test_note_est_eliminatoire_sur_ec(self):
        ec = ElementConstitutif(note_eliminatoire=Decimal('7.00'))
        self.assertTrue(ec.note_est_eliminatoire(Decimal('6.50')))
        self.assertFalse(ec.note_est_eliminatoire(Decimal('7.00')))
        self.assertFalse(ec.note_est_eliminatoire(Decimal('8.00')))
        self.assertFalse(ec.note_est_eliminatoire(None))

    def test_moyenne_cycle_ponderee(self):
        engine = DeliberationCycleMasterEngine.__new__(DeliberationCycleMasterEngine)
        moy = engine._moyenne_cycle(
            Decimal('12.00'), Decimal('14.00'),
            Decimal('60'), Decimal('60'),
        )
        self.assertEqual(moy, Decimal('13.00'))

    def test_analyser_ue_directe_vs_compensee(self):
        seuil = Decimal('10.00')
        resultat = {
            'notes_ue': {
                1: {'ue': SimpleNamespace(), 'note': Decimal('11.00'), 'valide': True},
                2: {'ue': SimpleNamespace(), 'note': Decimal('9.00'), 'valide': True},
            },
        }
        directes, compensees, non_validees = analyser_validation_ues(resultat, seuil)
        self.assertEqual(len(directes), 1)
        self.assertEqual(len(compensees), 1)
        self.assertEqual(len(non_validees), 0)

    @patch('deliberations.cycle_services.promotion_precedente')
    def test_peut_deliberer_cycle_sans_m1(self, mock_prev):
        mock_prev.return_value = None
        promo = SimpleNamespace(code='M2')
        annee = SimpleNamespace(annee_debut=2025)
        ok, msg = peut_deliberer_cycle_master(promo, annee, annee)
        self.assertFalse(ok)
        self.assertIn('Master 1', msg)
