# 📊 DONNÉES DE TEST INITIALISÉES

## ✅ Données créées avec succès

### Structure Académique
- **1 Faculté** : Faculté des Sciences et Techniques (FST)
- **1 Département** : Département d'Informatique (INFO)
- **1 Filière** : Mathématiques et Informatique (MI) - Niveau Licence
- **1 Parcours** : Licence 1 Mathématiques et Informatique (MI-L1)
- **1 Année Académique** : 2025-2026 (active)
- **1 Promotion** : MI-L1-2025-2026

### Maquette LMD
- **2 Semestres** : S1 et S2 (30 crédits ECTS chacun)
- **8 Unités d'Enseignement (UE)** :
  - **S1** : UE1 (Mathématiques Fondamentales), UE2 (Informatique Fondamentale), UE3 (Langues et Communication), UE4 (Méthodologie et Projet)
  - **S2** : UE5 (Mathématiques Appliquées), UE6 (Programmation Avancée), UE7 (Bases de Données), UE8 (Projet et Stage)
- **20 Éléments Constitutifs (EC)** répartis sur les 8 UE

### Étudiants
- **20 Étudiants** créés avec :
  - Numéros : ETU0001 à ETU0020
  - Noms et prénoms aléatoires
  - Emails : prenom.nom@student.edu
  - Dates de naissance entre 2000-2004
  - Statut : Actif
- **20 Inscriptions** pour la promotion MI-L1-2025-2026
- **20 Dossiers étudiants** (complets)
- **5 Types de documents** : CNI, Photo, Bac, Relevé, Certificat

### Évaluations
- **4 Types d'évaluation** :
  - CC (Contrôle Continu) - Coef 1
  - TP (Travaux Pratiques) - Coef 1
  - EXAM (Examen) - Coef 2
  - RATT (Rattrapage) - Coef 1
- **2 Sessions** : Session 1 pour S1 et S2
- **20 Évaluations** (CC et EXAM pour chaque EC du S1)
- **400 Notes** générées aléatoirement (8-18/20) pour les étudiants

### Délibérations
- **1 Paramètres LMD** configurés :
  - Seuil de validation : 10/20
  - Compensation intra-UE : Oui
  - Compensation intra-semestre : Oui
  - Compensation annuelle : Oui
  - Capitalisation UE et EC : Oui
  - Passage avec dettes : Oui (seuil : 24 crédits)
- **1 Délibération** créée pour la Session 1 du Semestre 1

---

## 🔐 COMPTE ADMINISTRATEUR

**Identifiants de connexion :**
- **Username** : `admin`
- **Password** : `admin123`
- **Email** : admin@university.edu

⚠️ **IMPORTANT** : Changez le mot de passe après la première connexion !

---

## 🚀 COMMENT TESTER

### 1. Démarrer le serveur
```bash
cd d:\djangoapp\venvmanya\gestacademia
python manage.py runserver
```

### 2. Se connecter
- Accéder à : `http://127.0.0.1:8000/`
- Se connecter avec : `admin` / `admin123`

### 3. Parcours de test suggéré

#### A. Structure Académique
1. **Facultés** : `/academics/facultes/`
   - Voir la liste (1 faculté)
   - Cliquer sur "Nouvelle Faculté" pour tester la création
   - Modifier ou supprimer une faculté

2. **Départements** : `/academics/departements/`
3. **Filières** : `/academics/filieres/`
4. **Parcours** : `/academics/parcours/`
5. **Années Académiques** : `/academics/annees-academiques/`
6. **Promotions** : `/academics/promotions/`

#### B. Maquette LMD
1. **Semestres** : `/academics/semestres/`
   - Voir les 2 semestres créés
2. **Unités d'Enseignement** : `/academics/ues/`
   - Voir les 8 UE (4 par semestre)
3. **Éléments Constitutifs** : `/academics/ecs/`
   - Voir les 20 EC répartis sur les UE

#### C. Étudiants
1. **Liste des Étudiants** : `/students/etudiants/`
   - Voir les 20 étudiants
   - Cliquer sur "Voir" pour voir le détail d'un étudiant
   - Tester la modification
2. **Inscriptions** : `/students/inscriptions/`
   - Voir les 20 inscriptions
3. **Dossiers** : `/students/dossiers/`
   - Voir les dossiers étudiants
4. **Documents** : `/students/documents/`
   - Ajouter des documents pour les étudiants

#### D. Évaluations
1. **Types d'Évaluation** : `/evaluations/types-evaluation/`
   - Voir les 4 types (CC, TP, EXAM, RATT)
2. **Sessions** : `/evaluations/sessions/`
   - Voir les 2 sessions créées
3. **Évaluations** : `/evaluations/evaluations/`
   - Voir les 20 évaluations
   - Cliquer sur "Saisir notes" pour tester la saisie en masse
4. **Notes** : `/evaluations/notes/`
   - Voir les 400 notes créées

#### E. Délibérations
1. **Paramètres LMD** : `/deliberations/parametres-lmd/`
   - Voir les paramètres configurés
2. **Délibérations** : `/deliberations/deliberations/`
   - Voir la délibération créée
   - Cliquer sur "Voir" pour voir le détail
   - Cliquer sur "Calculer" pour lancer le calcul des décisions
3. **Génération de Documents** : `/documents/...`
   - Tester la génération de PV et relevés

---

## 📋 DÉTAILS DES DONNÉES

### Étudiants créés
- **ETU0001** à **ETU0020**
- Noms aléatoires parmi : Alaoui, Benali, Chraibi, El Amrani, Fassi, etc.
- Prénoms aléatoires parmi : Ahmed, Fatima, Mohamed, Aicha, Hassan, etc.
- Tous inscrits dans la promotion **MI-L1-2025-2026**

### Notes générées
- **400 notes** au total
- Notes aléatoires entre **8.00 et 18.00** sur 20
- Environ **10% d'absents** (aléatoire)
- Réparties sur les **20 évaluations** (CC et EXAM)

### Structure des UE et EC

**Semestre 1 :**
- **UE1 - Mathématiques Fondamentales** (9 ECTS)
  - EC1.1 : Algèbre Linéaire (3 ECTS)
  - EC1.2 : Analyse (3 ECTS)
  - EC1.3 : Probabilités (3 ECTS)
- **UE2 - Informatique Fondamentale** (9 ECTS)
  - EC2.1 : Algorithmique (3 ECTS)
  - EC2.2 : Programmation Python (3 ECTS)
  - EC2.3 : Structures de Données (3 ECTS)
- **UE3 - Langues et Communication** (6 ECTS)
  - EC3.1 : Anglais (3 ECTS)
  - EC3.2 : Communication (3 ECTS)
- **UE4 - Méthodologie et Projet** (6 ECTS)
  - EC4.1 : Méthodologie de Travail (3 ECTS)
  - EC4.2 : Projet Tutoré (3 ECTS)

**Semestre 2 :**
- **UE5 - Mathématiques Appliquées** (9 ECTS)
  - EC5.1 : Statistiques (3 ECTS)
  - EC5.2 : Optimisation (3 ECTS)
  - EC5.3 : Mathématiques Discrètes (3 ECTS)
- **UE6 - Programmation Avancée** (9 ECTS)
  - EC6.1 : Programmation Orientée Objet (3 ECTS)
  - EC6.2 : Java (3 ECTS)
  - EC6.3 : Design Patterns (3 ECTS)
- **UE7 - Bases de Données** (6 ECTS)
  - EC7.1 : Modélisation (3 ECTS)
  - EC7.2 : SQL (3 ECTS)
- **UE8 - Projet et Stage** (6 ECTS)
  - EC8.1 : Projet de Fin d'Année (3 ECTS)
  - EC8.2 : Stage (3 ECTS)

---

## 🔄 RÉINITIALISER LES DONNÉES

Si vous voulez réinitialiser toutes les données :

```bash
python manage.py init_data --clear
```

Cela supprimera toutes les données existantes et recréera tout depuis le début.

---

## 📝 NOTES IMPORTANTES

1. **Les données sont cohérentes** : Toutes les relations entre modèles sont respectées
2. **Les dates sont réalistes** : Basées sur la date actuelle
3. **Les notes sont aléatoires** : Pour tester les calculs LMD
4. **Le compte admin existe** : Utilisez-le pour vous connecter

---

**✅ Vous êtes prêt à tester l'application complète !**
