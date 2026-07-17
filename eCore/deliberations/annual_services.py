"""
Moteur de délibération annuelle (agrégation S1 + S2).
"""
from decimal import Decimal

from academics.models import AnneeAcademique
from deliberations.decision_services import produire_decision_agregee
from deliberations.models import Deliberation, ParametresLMD
from deliberations.services import DeliberationEngine, mention_code_depuis_moyenne
from evaluations.models import Session
from students.models import Inscription, Student


class DeliberationAnnuelleError(Exception):
    """Erreur métier de la délibération annuelle."""


def session_finale_semestre(semestre, promotion=None, annee_academique=None):
    """Session utilisée pour la délibération semestrielle (S2 prioritaire)."""
    from deliberations.models import Deliberation

    if promotion:
        delib = (
            Deliberation.objects.filter(
                promotion=promotion,
                type_deliberation='semestrielle',
                statut='terminee',
                session__semestre=semestre,
            )
            .select_related('session')
            .order_by('-session__numero')
            .first()
        )
        return delib.session if delib else None

    annee = annee_academique or AnneeAcademique.get_active()
    base = {'semestre': semestre, 'deliberation_faite': True, 'active': True}
    if annee:
        base['annee_academique'] = annee

    s2 = Session.objects.filter(numero=2, **base).first()
    if s2:
        return s2
    return Session.objects.filter(numero=1, **base).first()


def deliberation_semestrielle_terminee(promotion, semestre):
    """Délibération semestrielle terminée pour la promotion sur ce semestre."""
    return Deliberation.objects.filter(
        promotion=promotion,
        type_deliberation='semestrielle',
        statut='terminee',
        session__semestre=semestre,
    ).exists()


def peut_deliberer_annuelle(promotion, annee_academique, semestre1, semestre2):
    """Vérifie les prérequis de la délibération annuelle."""
    if semestre1.pk == semestre2.pk:
        return False, 'Choisissez deux semestres distincts.'
    if semestre1.numero > semestre2.numero:
        semestre1, semestre2 = semestre2, semestre1

    for semestre in (semestre1, semestre2):
        if not deliberation_semestrielle_terminee(promotion, semestre):
            return False, (
                f'La délibération semestrielle du {semestre.code} doit être terminée '
                f'pour la promotion {promotion.code}.'
            )
        if not session_finale_semestre(semestre, promotion):
            return False, (
                f'Aucune session finalisée pour le {semestre.code}.'
            )

    return True, ''


class DeliberationAnnuelleEngine:
    """Calcule moyenne annuelle, crédits cumulés et décision de passage."""

    def __init__(self, promotion, annee_academique, semestre1, semestre2):
        self.promotion = promotion
        self.annee_academique = annee_academique
        if semestre1.numero > semestre2.numero:
            semestre1, semestre2 = semestre2, semestre1
        self.semestre1 = semestre1
        self.semestre2 = semestre2
        self.session1 = session_finale_semestre(semestre1, promotion)
        self.session2 = session_finale_semestre(semestre2, promotion)
        if not self.session1 or not self.session2:
            raise DeliberationAnnuelleError('Sessions semestrielles introuvables pour cette promotion.')
        self.engine1 = DeliberationEngine(self.session1, promotion)
        self.engine2 = DeliberationEngine(self.session2, promotion)
        try:
            self.parametres = ParametresLMD.objects.get(promotion=promotion)
        except ParametresLMD.DoesNotExist:
            self.parametres = ParametresLMD.objects.create(promotion=promotion)

    def _resultat_semestre(self, etudiant: Student, engine: DeliberationEngine):
        return engine.traiter_etudiant(etudiant)

    def _moyenne_annuelle(self, moy1, moy2, credits_tot1, credits_tot2):
        if moy1 is not None and moy2 is not None and credits_tot1 + credits_tot2 > 0:
            return (
                (moy1 * credits_tot1 + moy2 * credits_tot2) / (credits_tot1 + credits_tot2)
            ).quantize(Decimal('0.01'))
        if moy1 is not None:
            return moy1
        if moy2 is not None:
            return moy2
        return None

    def _credits_annuels(self, etudiant, r1, r2, moyenne_annuelle):
        """Crédits cumulés avec compensation annuelle optionnelle."""
        credits_obtenus = r1['credits_obtenus'] + r2['credits_obtenus']
        credits_totaux = r1['credits_totaux'] + r2['credits_totaux']

        if not self.parametres.compensation_annuelle or moyenne_annuelle is None:
            return credits_obtenus, credits_totaux

        seuil = self.parametres.seuil_validation
        if not self.engine1._note_depasse_seuil(moyenne_annuelle, seuil):
            return credits_obtenus, credits_totaux

        ues_vues = {}
        for engine, resultat in ((self.engine1, r1), (self.engine2, r2)):
            for ue_id, data in resultat['notes_ue'].items():
                ue = data['ue']
                if ue_id not in ues_vues:
                    ues_vues[ue_id] = {'ue': ue, 'valide': False, 'credits': Decimal('0.00')}
                if data['valide']:
                    ues_vues[ue_id]['valide'] = True
                    ues_vues[ue_id]['credits'] = ue.credits_ects

        total = Decimal('0.00')
        for data in ues_vues.values():
            ue = data['ue']
            if data['valide']:
                total += ue.credits_ects
            elif ue.compensation_autorisee and self.parametres.compensation_annuelle:
                total += ue.credits_ects

        total = min(total, credits_totaux).quantize(Decimal('0.01'))
        return max(credits_obtenus, total), credits_totaux

    def produire_decision(self, etudiant, r1, r2, moyenne_annuelle, credits_obtenus, credits_totaux):
        return produire_decision_agregee(
            [self.engine1, self.engine2],
            etudiant,
            [r1, r2],
            moyenne_annuelle,
            credits_obtenus,
            credits_totaux,
            multiplicateur_seuil=2,
        )

    def traiter_etudiant(self, etudiant: Student) -> dict:
        r1 = self._resultat_semestre(etudiant, self.engine1)
        r2 = self._resultat_semestre(etudiant, self.engine2)

        moyenne_annuelle = self._moyenne_annuelle(
            r1['moyenne_semestre'],
            r2['moyenne_semestre'],
            r1['credits_totaux'],
            r2['credits_totaux'],
        )
        credits_obtenus, credits_totaux = self._credits_annuels(
            etudiant, r1, r2, moyenne_annuelle,
        )
        decision = self.produire_decision(
            etudiant, r1, r2, moyenne_annuelle, credits_obtenus, credits_totaux,
        )

        return {
            'etudiant': etudiant,
            'resultat_s1': r1,
            'resultat_s2': r2,
            'moyenne_annuelle': moyenne_annuelle,
            'moyenne_semestre1': r1['moyenne_semestre'],
            'moyenne_semestre2': r2['moyenne_semestre'],
            'credits_semestre1': r1['credits_obtenus'],
            'credits_semestre2': r2['credits_obtenus'],
            'credits_obtenus': credits_obtenus,
            'credits_totaux': credits_totaux,
            'decision': decision,
            'mention': mention_code_depuis_moyenne(moyenne_annuelle),
        }

    def traiter_tous_etudiants(self):
        inscriptions = Inscription.objects.filter(
            classe__promotion=self.promotion,
            annee_academique=self.annee_academique,
        ).eligibles_listes().select_related('etudiant', 'classe')

        resultats = []
        for inscription in inscriptions:
            resultats.append(self.traiter_etudiant(inscription.etudiant))
        return resultats
