"""
Moteur de délibération du cycle Master (agrégation Master 1 + Master 2).
"""
from decimal import Decimal

from deliberations.annual_services import (
    DeliberationAnnuelleEngine,
    DeliberationAnnuelleError,
    deliberation_semestrielle_terminee,
    peut_deliberer_annuelle,
)
from deliberations.dettes_services import promotion_precedente, semestres_pour_promotion
from deliberations.decision_services import produire_decision_agregee
from deliberations.models import Deliberation, ParametresLMD
from deliberations.services import mention_code_depuis_moyenne
from students.models import Inscription, Student


class DeliberationCycleMasterError(Exception):
    """Erreur métier de la délibération cycle Master."""


def deliberation_annuelle_terminee(promotion, annee_academique):
    """Délibération annuelle terminée pour une promotion sur une année."""
    semestres = list(semestres_pour_promotion(promotion))
    if len(semestres) < 2:
        return False
    return Deliberation.objects.filter(
        promotion=promotion,
        type_deliberation=Deliberation.TYPE_ANNUELLE,
        annee_academique=annee_academique,
        semestre1=semestres[0],
        semestre2=semestres[1],
        statut='terminee',
    ).exists()


def peut_deliberer_cycle_master(promotion_m2, annee_m1, annee_m2):
    """Vérifie les prérequis de la délibération cycle Master (M1 + M2)."""
    promotion_m1 = promotion_precedente(promotion_m2)
    if not promotion_m1:
        return False, (
            f'La promotion {promotion_m2.code} n’a pas de promotion Master 1 précédente '
            f'dans la même filière.'
        )

    if annee_m1 and annee_m2 and annee_m1.annee_debut >= annee_m2.annee_debut:
        return False, 'L’année Master 1 doit être antérieure à l’année Master 2.'

    semestres_m1 = list(semestres_pour_promotion(promotion_m1))
    semestres_m2 = list(semestres_pour_promotion(promotion_m2))
    if len(semestres_m1) < 2 or len(semestres_m2) < 2:
        return False, 'Semestres LMD introuvables pour Master 1 ou Master 2.'

    ok_m1, msg_m1 = peut_deliberer_annuelle(
        promotion_m1, annee_m1, semestres_m1[0], semestres_m1[1],
    )
    if not ok_m1:
        return False, f'Master 1 : {msg_m1}'

    ok_m2, msg_m2 = peut_deliberer_annuelle(
        promotion_m2, annee_m2, semestres_m2[0], semestres_m2[1],
    )
    if not ok_m2:
        return False, f'Master 2 : {msg_m2}'

    if not deliberation_annuelle_terminee(promotion_m1, annee_m1):
        return False, (
            f'La délibération annuelle Master 1 ({promotion_m1.code}, {annee_m1.code}) '
            f'doit être terminée.'
        )

    if not deliberation_annuelle_terminee(promotion_m2, annee_m2):
        return False, (
            f'La délibération annuelle Master 2 ({promotion_m2.code}, {annee_m2.code}) '
            f'doit être terminée.'
        )

    return True, ''


class DeliberationCycleMasterEngine:
    """Calcule moyenne du cycle Master, crédits cumulés et décision de diplôme."""

    def __init__(self, promotion_m2, annee_m1, annee_m2):
        self.promotion_m2 = promotion_m2
        self.promotion_m1 = promotion_precedente(promotion_m2)
        self.annee_m1 = annee_m1
        self.annee_m2 = annee_m2

        if not self.promotion_m1:
            raise DeliberationCycleMasterError(
                f'Aucune promotion Master 1 pour {promotion_m2.code}.',
            )

        semestres_m1 = list(semestres_pour_promotion(self.promotion_m1))
        semestres_m2 = list(semestres_pour_promotion(self.promotion_m2))
        if len(semestres_m1) < 2 or len(semestres_m2) < 2:
            raise DeliberationCycleMasterError('Semestres Master 1 ou Master 2 introuvables.')

        try:
            self.engine_m1 = DeliberationAnnuelleEngine(
                self.promotion_m1, annee_m1, semestres_m1[0], semestres_m1[1],
            )
            self.engine_m2 = DeliberationAnnuelleEngine(
                self.promotion_m2, annee_m2, semestres_m2[0], semestres_m2[1],
            )
        except DeliberationAnnuelleError as exc:
            raise DeliberationCycleMasterError(str(exc)) from exc

        try:
            self.parametres = ParametresLMD.objects.get(promotion=promotion_m2)
        except ParametresLMD.DoesNotExist:
            self.parametres = ParametresLMD.objects.create(promotion=promotion_m2)

    def _moyenne_cycle(self, moy_m1, moy_m2, credits_tot_m1, credits_tot_m2):
        if moy_m1 is not None and moy_m2 is not None and credits_tot_m1 + credits_tot_m2 > 0:
            return (
                (moy_m1 * credits_tot_m1 + moy_m2 * credits_tot_m2)
                / (credits_tot_m1 + credits_tot_m2)
            ).quantize(Decimal('0.01'))
        if moy_m1 is not None:
            return moy_m1
        if moy_m2 is not None:
            return moy_m2
        return None

    def _credits_cycle(self, r_m1, r_m2, moyenne_cycle):
        """Crédits cumulés sur le cycle avec compensation optionnelle (paramètre annuel)."""
        credits_obtenus = r_m1['credits_obtenus'] + r_m2['credits_obtenus']
        credits_totaux = r_m1['credits_totaux'] + r_m2['credits_totaux']

        if not self.parametres.compensation_annuelle or moyenne_cycle is None:
            return credits_obtenus, credits_totaux

        seuil = self.parametres.seuil_validation
        if not self.engine_m1.engine1._note_depasse_seuil(moyenne_cycle, seuil):
            return credits_obtenus, credits_totaux

        ues_vues = {}
        for annual in (r_m1, r_m2):
            for resultat in (annual['resultat_s1'], annual['resultat_s2']):
                for ue_id, data in resultat['notes_ue'].items():
                    ue = data['ue']
                    if ue_id not in ues_vues:
                        ues_vues[ue_id] = {'ue': ue, 'valide': False}
                    if data['valide']:
                        ues_vues[ue_id]['valide'] = True

        total = Decimal('0.00')
        for data in ues_vues.values():
            ue = data['ue']
            if data['valide']:
                total += ue.credits_ects
            elif ue.compensation_autorisee and self.parametres.compensation_annuelle:
                total += ue.credits_ects

        total = min(total, credits_totaux).quantize(Decimal('0.01'))
        return max(credits_obtenus, total), credits_totaux

    def produire_decision(self, etudiant, r_m1, r_m2, moyenne_cycle, credits_obtenus, credits_totaux):
        resultats = [
            r_m1['resultat_s1'], r_m1['resultat_s2'],
            r_m2['resultat_s1'], r_m2['resultat_s2'],
        ]
        return produire_decision_agregee(
            [self.engine_m1.engine1, self.engine_m1.engine2, self.engine_m2.engine1, self.engine_m2.engine2],
            etudiant,
            resultats,
            moyenne_cycle,
            credits_obtenus,
            credits_totaux,
            multiplicateur_seuil=4,
        )

    def traiter_etudiant(self, etudiant: Student) -> dict:
        r_m1 = self.engine_m1.traiter_etudiant(etudiant)
        r_m2 = self.engine_m2.traiter_etudiant(etudiant)

        moyenne_m1 = r_m1['moyenne_annuelle']
        moyenne_m2 = r_m2['moyenne_annuelle']
        moyenne_cycle = self._moyenne_cycle(
            moyenne_m1,
            moyenne_m2,
            r_m1['credits_totaux'],
            r_m2['credits_totaux'],
        )
        credits_obtenus, credits_totaux = self._credits_cycle(r_m1, r_m2, moyenne_cycle)
        decision = self.produire_decision(
            etudiant, r_m1, r_m2, moyenne_cycle, credits_obtenus, credits_totaux,
        )

        return {
            'etudiant': etudiant,
            'resultat_m1': r_m1,
            'resultat_m2': r_m2,
            'moyenne_cycle': moyenne_cycle,
            'moyenne_m1': moyenne_m1,
            'moyenne_m2': moyenne_m2,
            'credits_m1': r_m1['credits_obtenus'],
            'credits_m2': r_m2['credits_obtenus'],
            'credits_obtenus': credits_obtenus,
            'credits_totaux': credits_totaux,
            'decision': decision,
            'mention': mention_code_depuis_moyenne(moyenne_cycle),
        }

    def traiter_tous_etudiants(self):
        inscriptions = Inscription.objects.filter(
            classe__promotion=self.promotion_m2,
            annee_academique=self.annee_m2,
        ).eligibles_listes().select_related('etudiant', 'classe')

        resultats = []
        for inscription in inscriptions:
            resultats.append(self.traiter_etudiant(inscription.etudiant))
        return resultats
