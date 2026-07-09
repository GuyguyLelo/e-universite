"""
Commande Django pour initialiser la base de données avec des données de test
Usage: python manage.py init_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import random

from academics.models import (
    Section, Filiere, Promotion, Classe, Local,
    AnneeAcademique, Semestre, UniteEnseignement, ElementConstitutif
)
from students.models import Student, Inscription, TypeDocument, DossierEtudiant
from evaluations.models import TypeEvaluation, Session, Evaluation, Note
from deliberations.models import ParametresLMD, Deliberation
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Initialise la base de données avec des données de test pour le système LMD'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprime toutes les données existantes avant d\'initialiser',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Suppression des données existantes...'))
            self.clear_data()
        
        self.stdout.write(self.style.SUCCESS('Début de l\'initialisation des données...'))
        
        # 1. Créer un utilisateur admin si nécessaire
        admin_user = self.create_admin_user()
        
        # 2. Structure académique (e-Core)
        section = self.create_section()
        filiere = self.create_filiere(section)
        promotion = self.create_promotion(filiere)
        local = self.create_local()
        classe = self.create_classe(promotion, local)
        annee_academique = self.create_annee_academique()
        
        # 3. Maquette LMD
        semestre1, semestre2 = self.create_semestres()
        ues_s1, ues_s2 = self.create_ues(semestre1, semestre2)
        self.create_ecs(ues_s1, ues_s2)
        
        # 4. Étudiants
        etudiants = self.create_etudiants(20)
        inscriptions = self.create_inscriptions(etudiants, classe, annee_academique)
        self.create_types_documents()
        self.create_dossiers(inscriptions)
        
        # 5. Évaluations
        types_eval = self.create_types_evaluation()
        session1, session2 = self.create_sessions(semestre1, semestre2, annee_academique)
        evaluations = self.create_evaluations(session1, types_eval)
        self.create_notes(etudiants, evaluations)
        
        # 6. Délibérations
        parametres = self.create_parametres_lmd(promotion)
        deliberation = self.create_deliberation(session1, promotion, admin_user)
        
        self.stdout.write(self.style.SUCCESS('\n[OK] Initialisation terminee avec succes!'))
        self.stdout.write(self.style.SUCCESS(f'\n[RESUME]'))
        self.stdout.write(f'   - {Section.objects.count()} Section(s)')
        self.stdout.write(f'   - {Filiere.objects.count()} Filière(s)')
        self.stdout.write(f'   - {Promotion.objects.count()} Promotion(s)')
        self.stdout.write(f'   - {Classe.objects.count()} Classe(s)')
        self.stdout.write(f'   - {Local.objects.count()} Local(aux)')
        self.stdout.write(f'   - {AnneeAcademique.objects.count()} Année(s) académique(s)')
        self.stdout.write(f'   - {Semestre.objects.count()} Semestre(s)')
        self.stdout.write(f'   - {UniteEnseignement.objects.count()} UE(s)')
        self.stdout.write(f'   - {ElementConstitutif.objects.count()} EC(s)')
        self.stdout.write(f'   - {Student.objects.count()} Étudiant(s)')
        self.stdout.write(f'   - {Inscription.objects.count()} Inscription(s)')
        self.stdout.write(f'   - {TypeEvaluation.objects.count()} Type(s) d\'évaluation')
        self.stdout.write(f'   - {Session.objects.count()} Session(s)')
        self.stdout.write(f'   - {Evaluation.objects.count()} Évaluation(s)')
        self.stdout.write(f'   - {Note.objects.count()} Note(s)')
        self.stdout.write(f'   - {Deliberation.objects.count()} Délibération(s)')
        self.stdout.write(self.style.SUCCESS(f'\n[INFO] Compte admin: username=admin, password=admin123'))

    def clear_data(self):
        """Supprime toutes les données existantes"""
        Note.objects.all().delete()
        Evaluation.objects.all().delete()
        Session.objects.all().delete()
        TypeEvaluation.objects.all().delete()
        DecisionJury = __import__('deliberations.models', fromlist=['DecisionJury']).DecisionJury
        DecisionJury.objects.all().delete()
        Deliberation.objects.all().delete()
        ParametresLMD.objects.all().delete()
        DocumentEtudiant = __import__('students.models', fromlist=['DocumentEtudiant']).DocumentEtudiant
        DocumentEtudiant.objects.all().delete()
        DossierEtudiant.objects.all().delete()
        TypeDocument.objects.all().delete()
        Inscription.objects.all().delete()
        Student.objects.all().delete()
        ElementConstitutif.objects.all().delete()
        UniteEnseignement.objects.all().delete()
        Semestre.objects.all().delete()
        Promotion.objects.all().delete()
        AnneeAcademique.objects.all().delete()
        Filiere.objects.all().delete()
        Classe.objects.all().delete()
        Local.objects.all().delete()
        Section.objects.all().delete()

    def create_admin_user(self):
        """Crée un utilisateur administrateur"""
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@university.edu',
                'first_name': 'Admin',
                'last_name': 'System',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS('[OK] Utilisateur admin cree'))
        return user

    def create_section(self):
        """Crée une section"""
        section, created = Section.objects.get_or_create(
            code='L',
            defaults={
                'nom': 'Licence',
                'description': 'Cycle Licence',
                'active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Section creee'))
        return section

    def create_filiere(self, section):
        """Crée une filière"""
        filiere, created = Filiere.objects.get_or_create(
            code='CONC',
            defaults={
                'section': section,
                'nom': 'Conception',
                'description': 'Filière Conception',
                'active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Filiere creee'))
        return filiere

    def create_annee_academique(self):
        """Crée une année académique"""
        annee_courante = date.today().year
        annee, created = AnneeAcademique.objects.get_or_create(
            code=f'{annee_courante}-{annee_courante+1}',
            defaults={
                'annee_debut': annee_courante,
                'annee_fin': annee_courante + 1,
                'date_debut': date(annee_courante, 9, 1),
                'date_fin': date(annee_courante + 1, 8, 31),
                'active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Annee academique creee'))
        return annee

    def create_promotion(self, filiere):
        """Crée une promotion (niveau)"""
        promotion, created = Promotion.objects.get_or_create(
            code='P1',
            defaults={
                'filiere': filiere,
                'nom': 'Première',
                'ordre': 1,
                'active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Promotion creee'))
        return promotion

    def create_local(self):
        """Crée un local"""
        local, created = Local.objects.get_or_create(
            code='L14',
            defaults={
                'nom': 'Local 14',
                'capacite': 50,
                'active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Local cree'))
        return local

    def create_classe(self, promotion, local):
        """Crée une classe"""
        classe, created = Classe.objects.get_or_create(
            promotion=promotion,
            code='A',
            defaults={
                'local': local,
                'nom': 'Classe A',
                'effectif_max': 50,
                'active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Classe creee'))
        return classe

    def create_semestres(self):
        """Crée les semestres du catalogue LMD"""
        semestre1, created1 = Semestre.objects.get_or_create(
            numero=1,
            defaults={
                'code': 'S1',
                'nom': 'Semestre 1',
                'credits_ects': 30,
                'date_debut': date.today() - timedelta(days=120),
                'date_fin': date.today() - timedelta(days=30),
                'active': True
            }
        )

        semestre2, created2 = Semestre.objects.get_or_create(
            numero=2,
            defaults={
                'code': 'S2',
                'nom': 'Semestre 2',
                'credits_ects': 30,
                'date_debut': date.today() - timedelta(days=30),
                'date_fin': date.today() + timedelta(days=120),
                'active': True
            }
        )
        
        if created1 or created2:
            self.stdout.write(self.style.SUCCESS('[OK] Semestres crees'))
        return semestre1, semestre2

    def create_ues(self, semestre1, semestre2):
        """Crée les Unités d'Enseignement"""
        ues_s1 = []
        ues_s2 = []
        
        # UE pour S1
        ue_data_s1 = [
            ('UE1', 'Mathématiques Fondamentales', Decimal('9.00'), Decimal('3.00')),
            ('UE2', 'Informatique Fondamentale', Decimal('9.00'), Decimal('3.00')),
            ('UE3', 'Langues et Communication', Decimal('6.00'), Decimal('2.00')),
            ('UE4', 'Méthodologie et Projet', Decimal('6.00'), Decimal('2.00')),
        ]
        
        for code, nom, credits, coef in ue_data_s1:
            ue, _ = UniteEnseignement.objects.get_or_create(
                semestre=semestre1,
                code=code,
                defaults={
                    'nom': nom,
                    'credits_ects': credits,
                    'coefficient': coef,
                    'seuil_validation': Decimal('10.00'),
                    'compensation_autorisee': True,
                    'capitalisable': True,
                    'active': True
                }
            )
            ues_s1.append(ue)
        
        # UE pour S2
        ue_data_s2 = [
            ('UE5', 'Mathématiques Appliquées', Decimal('9.00'), Decimal('3.00')),
            ('UE6', 'Programmation Avancée', Decimal('9.00'), Decimal('3.00')),
            ('UE7', 'Bases de Données', Decimal('6.00'), Decimal('2.00')),
            ('UE8', 'Projet et Stage', Decimal('6.00'), Decimal('2.00')),
        ]
        
        for code, nom, credits, coef in ue_data_s2:
            ue, _ = UniteEnseignement.objects.get_or_create(
                semestre=semestre2,
                code=code,
                defaults={
                    'nom': nom,
                    'credits_ects': credits,
                    'coefficient': coef,
                    'seuil_validation': Decimal('10.00'),
                    'compensation_autorisee': True,
                    'capitalisable': True,
                    'active': True
                }
            )
            ues_s2.append(ue)
        
        self.stdout.write(self.style.SUCCESS('[OK] Unites d\'Enseignement creees'))
        return ues_s1, ues_s2

    def create_ecs(self, ues_s1, ues_s2):
        """Crée les Éléments Constitutifs"""
        # EC pour S1
        ecs_data = {
            ues_s1[0]: [  # UE1 - Mathématiques Fondamentales
                ('EC1.1', 'Algèbre Linéaire', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC1.2', 'Analyse', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC1.3', 'Probabilités', Decimal('3.00'), Decimal('1.00'), 30),
            ],
            ues_s1[1]: [  # UE2 - Informatique Fondamentale
                ('EC2.1', 'Algorithmique', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC2.2', 'Programmation Python', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC2.3', 'Structures de Données', Decimal('3.00'), Decimal('1.00'), 30),
            ],
            ues_s1[2]: [  # UE3 - Langues et Communication
                ('EC3.1', 'Anglais', Decimal('3.00'), Decimal('1.00'), 20),
                ('EC3.2', 'Communication', Decimal('3.00'), Decimal('1.00'), 20),
            ],
            ues_s1[3]: [  # UE4 - Méthodologie et Projet
                ('EC4.1', 'Méthodologie de Travail', Decimal('3.00'), Decimal('1.00'), 20),
                ('EC4.2', 'Projet Tutoré', Decimal('3.00'), Decimal('1.00'), 20),
            ],
            ues_s2[0]: [  # UE5 - Mathématiques Appliquées
                ('EC5.1', 'Statistiques', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC5.2', 'Optimisation', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC5.3', 'Mathématiques Discrètes', Decimal('3.00'), Decimal('1.00'), 30),
            ],
            ues_s2[1]: [  # UE6 - Programmation Avancée
                ('EC6.1', 'Programmation Orientée Objet', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC6.2', 'Java', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC6.3', 'Design Patterns', Decimal('3.00'), Decimal('1.00'), 30),
            ],
            ues_s2[2]: [  # UE7 - Bases de Données
                ('EC7.1', 'Modélisation', Decimal('3.00'), Decimal('1.00'), 30),
                ('EC7.2', 'SQL', Decimal('3.00'), Decimal('1.00'), 30),
            ],
            ues_s2[3]: [  # UE8 - Projet et Stage
                ('EC8.1', 'Projet de Fin d\'Année', Decimal('3.00'), Decimal('1.00'), 20),
                ('EC8.2', 'Stage', Decimal('3.00'), Decimal('1.00'), 20),
            ],
        }
        
        total_ecs = 0
        for ue, ecs_list in ecs_data.items():
            for code, nom, credits, coef, vh in ecs_list:
                _, created = ElementConstitutif.objects.get_or_create(
                    ue=ue,
                    code=code,
                    defaults={
                        'nom': nom,
                        'credits_ects': credits,
                        'coefficient': coef,
                        'volume_horaire': vh,
                        'seuil_validation': Decimal('10.00'),
                        'compensation_autorisee': True,
                        'capitalisable': True,
                        'active': True
                    }
                )
                if created:
                    total_ecs += 1
        
        self.stdout.write(self.style.SUCCESS(f'[OK] {total_ecs} Elements Constitutifs crees'))

    def create_etudiants(self, nombre=20):
        """Crée des étudiants"""
        prenoms = ['Ahmed', 'Fatima', 'Mohamed', 'Aicha', 'Hassan', 'Sanae', 'Youssef', 'Khadija',
                   'Omar', 'Laila', 'Karim', 'Nadia', 'Bilal', 'Sara', 'Amine', 'Salma', 'Mehdi', 'Imane']
        noms = ['Alaoui', 'Benali', 'Chraibi', 'El Amrani', 'Fassi', 'Idrissi', 'Kettani', 'Lamrani',
                'Mansouri', 'Naciri', 'Ouali', 'Rahali', 'Saadi', 'Tazi', 'Zahiri', 'Bennani']
        
        etudiants = []
        for i in range(1, nombre + 1):
            numero = f'ETU{str(i).zfill(4)}'
            prenom = random.choice(prenoms)
            nom = random.choice(noms)
            
            etudiant, created = Student.objects.get_or_create(
                numero_etudiant=numero,
                defaults={
                    'nom': nom,
                    'prenom': prenom,
                    'email': f'{prenom.lower()}.{nom.lower()}@student.edu',
                    'date_naissance': date(2000 + random.randint(0, 4), random.randint(1, 12), random.randint(1, 28)),
                    'lieu_naissance': random.choice(['Casablanca', 'Rabat', 'Fès', 'Marrakech', 'Tanger']),
                    'sexe': random.choice(['M', 'F']),
                    'nationalite': 'Marocaine',
                    'telephone': f'06{random.randint(10000000, 99999999)}',
                    'statut': 'actif'
                }
            )
            if created:
                etudiants.append(etudiant)
        
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(etudiants)} Etudiants crees'))
        return etudiants

    def create_inscriptions(self, etudiants, classe, annee_academique):
        """Crée des inscriptions"""
        inscriptions = []
        for i, etudiant in enumerate(etudiants):
            inscription, created = Inscription.objects.get_or_create(
                etudiant=etudiant,
                classe=classe,
                annee_academique=annee_academique,
                defaults={
                    'numero_inscription': f'INS{str(i+1).zfill(4)}',
                    'statut': 'inscrit',
                    'date_inscription': date.today() - timedelta(days=150),
                    'frais_inscription': Decimal('2000.00'),
                    'frais_payes': Decimal('2000.00'),
                    'dossier_complet': True
                }
            )
            if created:
                inscriptions.append(inscription)
        
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(inscriptions)} Inscriptions creees'))
        return inscriptions

    def create_types_documents(self):
        """Crée les types de documents"""
        types = [
            ('CNI', 'Copie Carte Nationale d\'Identité', True, 1),
            ('PHOTO', 'Photo d\'identité', True, 2),
            ('BAC', 'Copie du Baccalauréat', True, 3),
            ('RELEVE', 'Relevé de notes du Bac', True, 4),
            ('CERTIF', 'Certificat de scolarité', False, 5),
        ]
        
        for code, nom, obligatoire, ordre in types:
            TypeDocument.objects.get_or_create(
                code=code,
                defaults={
                    'nom': nom,
                    'obligatoire': obligatoire,
                    'ordre': ordre,
                    'active': True
                }
            )
        
        self.stdout.write(self.style.SUCCESS('[OK] Types de documents crees'))

    def create_dossiers(self, inscriptions):
        """Crée les dossiers étudiants"""
        for inscription in inscriptions:
            DossierEtudiant.objects.get_or_create(
                inscription=inscription,
                defaults={
                    'date_ouverture': inscription.date_inscription,
                    'statut': 'complet'
                }
            )
        self.stdout.write(self.style.SUCCESS('[OK] Dossiers etudiants crees'))

    def create_types_evaluation(self):
        """Crée les types d'évaluation"""
        types = [
            ('TP', 'Travaux Journaliers', Decimal('1.00'), Decimal('10.00'), 1),
            ('EXAM', 'Examen du semestre', Decimal('1.00'), Decimal('10.00'), 2),
            ('RATT', 'Rattrapage (examen)', Decimal('1.00'), Decimal('10.00'), 3),
        ]
        
        types_eval = []
        for code, nom, coef, note_max, ordre in types:
            type_eval, _ = TypeEvaluation.objects.get_or_create(
                code=code,
                defaults={
                    'nom': nom,
                    'coefficient': coef,
                    'note_max': note_max,
                    'ordre': ordre,
                    'active': True
                }
            )
            types_eval.append(type_eval)
        
        self.stdout.write(self.style.SUCCESS('[OK] Types d\'evaluation crees'))
        return types_eval

    def create_sessions(self, semestre1, semestre2, annee_academique):
        """Crée les sessions (codes courts pour respecter la limite du champ)."""
        code_s1 = f'{semestre1.code}-S1'[:50]  # tronquer si > 50
        code_s2 = f'{semestre2.code}-S1'[:50]
        session1, created1 = Session.objects.get_or_create(
            semestre=semestre1,
            numero=1,
            annee_academique=annee_academique,
            defaults={
                'code': code_s1,
                'nom': 'Session 1 - Semestre 1',
                'date_debut': semestre1.date_debut + timedelta(days=90),
                'date_fin': semestre1.date_debut + timedelta(days=100),
                'date_deliberation': semestre1.date_debut + timedelta(days=105),
                'deliberation_faite': False,
                'verrouillee': False,
                'active': True
            }
        )
        
        session2, created2 = Session.objects.get_or_create(
            semestre=semestre2,
            numero=1,
            annee_academique=annee_academique,
            defaults={
                'code': code_s2,
                'nom': 'Session 1 - Semestre 2',
                'date_debut': semestre2.date_debut + timedelta(days=90),
                'date_fin': semestre2.date_debut + timedelta(days=100),
                'deliberation_faite': False,
                'verrouillee': False,
                'active': True
            }
        )
        
        if created1 or created2:
            self.stdout.write(self.style.SUCCESS('[OK] Sessions creees'))
        return session1, session2

    def create_evaluations(self, session, types_eval):
        """Crée des évaluations pour les EC du semestre"""
        semestre = session.semestre
        ecs = ElementConstitutif.objects.filter(ue__semestre=semestre)
        
        evaluations = []
        for ec in ecs:
            # Créer une évaluation TJ (TP) et une EXAM pour chaque EC
            for type_eval in [types_eval[0], types_eval[1]]:  # Travaux Journaliers et EXAM
                eval_obj, created = Evaluation.objects.get_or_create(
                    ec=ec,
                    session=session,
                    type_evaluation=type_eval,
                    defaults={
                        'annee_academique': session.annee_academique,
                        'code': Evaluation.build_code(ec, session, type_eval),
                        'nom': Evaluation.build_nom(type_eval, ec, session),
                        'date_evaluation': session.date_debut + timedelta(days=random.randint(0, 10)),
                        'coefficient': type_eval.coefficient,
                        'note_max': type_eval.note_max,
                        'active': True
                    }
                )
                if created:
                    evaluations.append(eval_obj)
        
        self.stdout.write(self.style.SUCCESS(f'[OK] {len(evaluations)} Evaluations creees'))
        return evaluations

    def create_notes(self, etudiants, evaluations):
        """Crée des notes aléatoires pour les étudiants"""
        notes_crees = 0
        for evaluation in evaluations:
            for etudiant in etudiants:
                # 10% de chance d'être absent
                absent = random.random() < 0.1
                note_value = None if absent else Decimal(str(round(random.uniform(8.0, 18.0), 2)))
                
                note, created = Note.objects.get_or_create(
                    etudiant=etudiant,
                    evaluation=evaluation,
                    defaults={
                        'note': note_value,
                        'note_sur': evaluation.note_max,
                        'absent': absent,
                        'justifie': absent and random.random() < 0.5,
                        'saisie_par': User.objects.filter(is_superuser=True).first()
                    }
                )
                if created:
                    notes_crees += 1
        
        self.stdout.write(self.style.SUCCESS(f'[OK] {notes_crees} Notes creees'))

    def create_parametres_lmd(self, promotion):
        """Crée les paramètres LMD"""
        parametres, created = ParametresLMD.objects.get_or_create(
            promotion=promotion,
            defaults={
                'seuil_validation': Decimal('10.00'),
                'compensation_intra_ue': True,
                'compensation_intra_semestre': True,
                'compensation_annuelle': True,
                'capitalisation_ue': True,
                'capitalisation_ec': True,
                'passage_avec_dettes': True,
                'seuil_credits_minimum': Decimal('24.00')
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Parametres LMD crees'))
        return parametres

    def create_deliberation(self, session, promotion, president):
        """Crée une délibération"""
        deliberation, created = Deliberation.objects.get_or_create(
            session=session,
            promotion=promotion,
            defaults={
                'date_deliberation': session.date_deliberation,
                'president_jury': president,
                'statut': 'en_cours'
            }
        )
        if created:
            # Ajouter des membres du jury
            membres = User.objects.filter(is_staff=True)[:3]
            deliberation.membres_jury.set(membres)
            self.stdout.write(self.style.SUCCESS('[OK] Deliberation creee'))
        return deliberation
