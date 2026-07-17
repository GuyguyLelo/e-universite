"""
Moteur de délibération LMD - Service de calcul des notes, compensation, capitalisation
"""
from decimal import Decimal
from django.db.models import Q, Sum, Avg, Count
from django.core.exceptions import ValidationError
from academics.models import Semestre, UniteEnseignement, ElementConstitutif
from students.models import Student, Inscription
from evaluations.models import (
    Session, Evaluation, Note, NoteEC, NoteUE, TypeEvaluation
)
from evaluations.calcul_notes import (
    calculer_note_ec as calculer_note_ec_depuis_evaluations,
    calculer_note_ec_combine_sessions,
)
from deliberations.models import ParametresLMD, Deliberation, DecisionJury
from deliberations.decision_services import produire_decision_semestre


def mention_code_depuis_moyenne(moyenne):
    """Convertit une moyenne en code mention DecisionJury."""
    if moyenne is None:
        return ''
    if moyenne >= Decimal('16'):
        return 'tres_bien'
    if moyenne >= Decimal('14'):
        return 'bien'
    if moyenne >= Decimal('12'):
        return 'assez_bien'
    if moyenne >= Decimal('10'):
        return 'passable'
    return ''


class DeliberationEngine:
    """
    Moteur de délibération LMD
    
    Responsabilités :
    1. Calculer les notes EC (moyenne TJ + examen du semestre, ou pondérée sinon)
    2. Calculer les notes UE (moyenne pondérée des EC)
    3. Calculer les moyennes de semestre
    4. Appliquer les compensations (intra-UE, intra-semestre, annuelle)
    5. Gérer la capitalisation (UE/EC validés)
    6. Calculer les crédits obtenus
    7. Produire les décisions finales
    """

    def __init__(self, session: Session, promotion):
        self.session = session
        self.semestre = session.semestre
        self.promotion = promotion
        self.filiere_id = getattr(getattr(promotion, 'filiere', None), 'id', None)
        self.session_principale = (
            Session.objects.filter(
                semestre=self.semestre,
                numero=1,
                annee_academique=self.session.annee_academique,
            ).first()
            if session.numero == 2 else None
        )
        self.mode_final = session.numero == 2 and self.session_principale is not None
        
        # Récupérer les paramètres LMD
        try:
            self.parametres = ParametresLMD.objects.get(promotion=self.promotion)
        except ParametresLMD.DoesNotExist:
            # Créer des paramètres par défaut
            self.parametres = ParametresLMD.objects.create(
                promotion=self.promotion,
                seuil_validation=Decimal('10.00'),
                compensation_intra_ue=True,
                compensation_intra_semestre=True,
                compensation_annuelle=True,
                capitalisation_ue=True,
                capitalisation_ec=True,
                passage_avec_dettes=True,
                seuil_credits_minimum=30
            )

    def _note_depasse_seuil(self, note: Decimal, seuil: Decimal) -> bool:
        """Un crédit est validé si la note est supérieure ou égale au seuil."""
        return note is not None and note >= seuil

    def _ues_semestre_qs(self):
        """UE du semestre, limitées à la filière de la promotion si connue."""
        qs = UniteEnseignement.objects.filter(semestre=self.semestre, active=True)
        if self.filiere_id:
            qs = qs.filter(filiere_id=self.filiere_id)
        return qs.order_by('ordre', 'code')

    def _ecs_semestre_qs(self):
        """EC du semestre (et de la filière promotion)."""
        return ElementConstitutif.objects.filter(
            ue__in=self._ues_semestre_qs(),
            active=True,
        ).select_related('ue')

    def credits_totaux_semestre(self) -> Decimal:
        return sum((ue.credits_ects for ue in self._ues_semestre_qs()), Decimal('0.00'))

    def _plafonner_credits(self, credits: Decimal) -> Decimal:
        plafond = self.credits_totaux_semestre()
        if plafond <= 0:
            return credits.quantize(Decimal('0.01'))
        return min(credits, plafond).quantize(Decimal('0.01'))

    def calculer_note_ec(self, etudiant: Student, ec: ElementConstitutif, session=None) -> Decimal:
        """
        Calcule la note finale d'un étudiant à un EC.

        Session principale : TJ et examen sur /10, moyenne sur /20.
        Autres cas (rattrapage seul, TP…) : moyenne pondérée des évaluations présentes.
        """
        session = session or self.session
        evaluations = Evaluation.objects.filter(
            ec=ec,
            session=session,
            active=True,
        ).select_related('type_evaluation')
        return calculer_note_ec_depuis_evaluations(etudiant, evaluations)

    def calculer_note_ec_retenue(self, etudiant: Student, ec: ElementConstitutif) -> Decimal:
        """
        Note EC finale : TJ (session 1) + examen ou rattrapage selon la règle < 10/10.
        """
        if not self.mode_final:
            return self.calculer_note_ec(etudiant, ec)
        evals_s1 = Evaluation.objects.filter(
            ec=ec,
            session=self.session_principale,
            active=True,
        ).select_related('type_evaluation')
        evals_s2 = Evaluation.objects.filter(
            ec=ec,
            session=self.session,
            active=True,
        ).select_related('type_evaluation')
        return calculer_note_ec_combine_sessions(etudiant, evals_s1, evals_s2)

    def _note_ec_effective(self, etudiant: Student, ec: ElementConstitutif) -> Decimal:
        """Note EC utilisée pour la délibération (avec fusion S1/S2 si applicable)."""
        if self.mode_final:
            return self.calculer_note_ec_retenue(etudiant, ec)
        return self.calculer_note_ec(etudiant, ec)

    def calculer_note_ue(self, etudiant: Student, ue: UniteEnseignement) -> Decimal:
        """
        Calcule la note finale d'un étudiant à une UE
        Note = moyenne pondérée des EC de l'UE
        """
        ecs = ElementConstitutif.objects.filter(ue=ue, active=True)
        
        if not ecs.exists():
            return None
        
        total_pondere = Decimal('0.00')
        total_coefficients = Decimal('0.00')
        
        for ec in ecs:
            note_ec = self._note_ec_effective(etudiant, ec)
            
            if note_ec is None:
                continue
            
            coefficient = ec.coefficient
            total_pondere += note_ec * coefficient
            total_coefficients += coefficient
        
        if total_coefficients == 0:
            return None
        
        note_finale = total_pondere / total_coefficients
        return note_finale.quantize(Decimal('0.01'))

    def valider_ec(self, etudiant: Student, ec: ElementConstitutif, note: Decimal) -> bool:
        """
        Détermine si un EC est validé pour un étudiant
        """
        seuil = ec.seuil_validation or self.parametres.seuil_validation

        if note is None:
            return False

        if ec.note_est_eliminatoire(note):
            return False

        # Validation directe (note ≥ seuil)
        if self._note_depasse_seuil(note, seuil):
            return True

        if not ec.compensation_autorisee:
            return False

        ue = ec.ue

        # Validation par compensation intra-UE
        if self.parametres.compensation_intra_ue:
            note_ue = self.calculer_note_ue(etudiant, ue)
            seuil_ue = ue.seuil_validation or self.parametres.seuil_validation
            if self._note_depasse_seuil(note_ue, seuil_ue):
                return True

        # UE validée (y compris par compensation semestrielle) → EC capitalisé
        note_ue = self.calculer_note_ue(etudiant, ue)
        if note_ue is not None and self.valider_ue(etudiant, ue, note_ue):
            return True

        return False

    def valider_ue(self, etudiant: Student, ue: UniteEnseignement, note: Decimal) -> bool:
        """
        Détermine si une UE est validée pour un étudiant
        """
        seuil = ue.seuil_validation or self.parametres.seuil_validation
        
        if note is None:
            return False
        
        # Validation directe (note ≥ seuil)
        if self._note_depasse_seuil(note, seuil):
            return True
        
        # Validation par compensation intra-semestre (si autorisée)
        if ue.compensation_autorisee and self.parametres.compensation_intra_semestre:
            moyenne_semestre = self.calculer_moyenne_semestre(etudiant)
            if self._note_depasse_seuil(moyenne_semestre, self.parametres.seuil_validation):
                return True
        
        return False

    def calculer_moyenne_semestre(self, etudiant: Student) -> Decimal:
        """
        Calcule la moyenne du semestre (moyenne pondérée des UE)
        """
        ues = self._ues_semestre_qs()
        
        if not ues.exists():
            return None
        
        total_pondere = Decimal('0.00')
        total_coefficients = Decimal('0.00')
        
        for ue in ues:
            note_ue = self.calculer_note_ue(etudiant, ue)
            
            if note_ue is None:
                continue
            
            coefficient = ue.coefficient
            total_pondere += note_ue * coefficient
            total_coefficients += coefficient
        
        if total_coefficients == 0:
            return None
        
        moyenne = total_pondere / total_coefficients
        return moyenne.quantize(Decimal('0.01'))

    def calculer_credits_obtenus(self, etudiant: Student) -> Decimal:
        """
        Crédits capitalisés du semestre : UE validée (crédits UE) ou, à défaut,
        EC validés individuellement (sans double comptage), plafonnés au total du semestre.
        """
        total = Decimal('0.00')

        for ue in self._ues_semestre_qs():
            note_ue = self.calculer_note_ue(etudiant, ue)
            if note_ue is not None and self.valider_ue(etudiant, ue, note_ue):
                total += ue.credits_ects
                continue

            if not self.parametres.capitalisation_ec:
                continue

            seuil = ue.seuil_validation or self.parametres.seuil_validation
            for ec in ElementConstitutif.objects.filter(ue=ue, active=True):
                if not ec.capitalisable:
                    continue
                note_ec = self._note_ec_effective(etudiant, ec)
                seuil_ec = ec.seuil_validation or seuil
                if note_ec is not None and self._note_depasse_seuil(note_ec, seuil_ec):
                    total += ec.credits_ects

        return self._plafonner_credits(total)

    def traiter_etudiant(self, etudiant: Student) -> dict:
        """
        Traite toutes les notes d'un étudiant pour le semestre
        Retourne un dictionnaire avec toutes les informations calculées
        """
        resultat = {
            'etudiant': etudiant,
            'notes_ec': {},
            'notes_ue': {},
            'moyenne_semestre': None,
            'credits_obtenus': Decimal('0.00'),
            'credits_totaux': Decimal('30.00'),
            'ues_validees': [],
            'ecs_valides': [],
        }
        
        # Calculer les notes EC
        ecs = self._ecs_semestre_qs()
        
        for ec in ecs:
            note_ec = self._note_ec_effective(etudiant, ec)
            valide = self.valider_ec(etudiant, ec, note_ec) if note_ec else False
            
            resultat['notes_ec'][ec.id] = {
                'ec': ec,
                'note': note_ec,
                'valide': valide,
                'est_eliminatoire': ec.note_est_eliminatoire(note_ec),
                'credits': ec.credits_ects if valide else Decimal('0.00'),
            }
            
            if valide:
                resultat['ecs_valides'].append(ec)
        
        # Calculer les notes UE
        ues = self._ues_semestre_qs()
        
        for ue in ues:
            note_ue = self.calculer_note_ue(etudiant, ue)
            valide = self.valider_ue(etudiant, ue, note_ue) if note_ue else False
            
            resultat['notes_ue'][ue.id] = {
                'ue': ue,
                'note': note_ue,
                'valide': valide,
                'credits': ue.credits_ects if valide else Decimal('0.00'),
            }
            
            if valide:
                resultat['ues_validees'].append(ue)
        
        # Calculer la moyenne du semestre
        resultat['moyenne_semestre'] = self.calculer_moyenne_semestre(etudiant)
        
        # Crédits du semestre (plafonnés à 30 ECTS de la filière)
        resultat['credits_totaux'] = self.credits_totaux_semestre()
        resultat['credits_obtenus'] = self.calculer_credits_obtenus(etudiant)
        
        return resultat

    def sauvegarder_notes_calculees(self, etudiant: Student, resultat: dict):
        """
        Sauvegarde les notes calculées dans la base de données
        """
        # Sauvegarder les notes EC
        for ec_id, data in resultat['notes_ec'].items():
            ec = data['ec']
            note_ec, created = NoteEC.objects.update_or_create(
                etudiant=etudiant,
                ec=ec,
                session=self.session,
                defaults={
                    'note_finale': data['note'],
                    'credits_obtenus': data['credits'],
                    'valide': data['valide'],
                    'capitalise': data['valide'] and ec.capitalisable,
                    'calculee_auto': True,
                }
            )
        
        # Sauvegarder les notes UE
        for ue_id, data in resultat['notes_ue'].items():
            ue = data['ue']
            note_ue, created = NoteUE.objects.update_or_create(
                etudiant=etudiant,
                ue=ue,
                session=self.session,
                defaults={
                    'note_finale': data['note'],
                    'credits_obtenus': data['credits'],
                    'valide': data['valide'],
                    'capitalise': data['valide'] and ue.capitalisable,
                    'calculee_auto': True,
                }
            )

    def produire_decision(self, etudiant: Student, resultat: dict) -> str:
        """
        Produit la décision finale pour un étudiant (barème institutionnel).
        Voir deliberations.decision_services pour le détail des conditions.
        """
        return produire_decision_semestre(self, etudiant, resultat)

    def traiter_tous_etudiants(self):
        """
        Traite tous les étudiants de la promotion pour cette session
        """
        inscriptions = Inscription.objects.filter(
            classe__promotion=self.promotion,
            statut='inscrit'
        ).select_related('etudiant', 'classe')
        resultats = []
        
        for inscription in inscriptions:
            etudiant = inscription.etudiant
            resultat = self.traiter_etudiant(etudiant)
            self.sauvegarder_notes_calculees(etudiant, resultat)
            resultat['decision'] = self.produire_decision(etudiant, resultat)
            resultats.append(resultat)
        
        return resultats
