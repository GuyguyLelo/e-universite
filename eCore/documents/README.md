# Services de Génération de Documents PDF

Ce module fournit des services pour générer des documents PDF officiels avec ReportLab.

## Installation

Assurez-vous d'avoir installé les dépendances :

```bash
pip install reportlab Pillow
```

## Services Disponibles

### 1. Relevé de Notes (`ReleveNotesGenerator`)

Génère un relevé de notes détaillé pour un étudiant et une session.

**Utilisation :**
```python
from documents.services import ReleveNotesGenerator
from io import BytesIO

buffer = BytesIO()
generator = ReleveNotesGenerator(etudiant, session, buffer)
generator.generate()

# Le buffer contient maintenant le PDF
```

**URL :** `/documents/releve-notes/<etudiant_id>/<session_id>/`

**Contenu du document :**
- En-tête avec titre et année académique
- Informations étudiant (numéro, nom, prénom, date de naissance)
- Informations académiques (filière, parcours, semestre, session)
- Tableau détaillé des notes (UE, EC, notes, crédits, statut)
- Résumé (moyenne semestre, crédits obtenus, pourcentage)

### 2. Procès-Verbal de Délibération (`ProcesVerbalGenerator`)

Génère un procès-verbal officiel de délibération du jury.

**Utilisation :**
```python
from documents.services import ProcesVerbalGenerator
from io import BytesIO

buffer = BytesIO()
generator = ProcesVerbalGenerator(deliberation, buffer)
generator.generate()
```

**URL :** `/documents/proces-verbal/<deliberation_id>/`

**Contenu du document :**
- En-tête avec titre et session
- Informations de délibération (date, promotion, semestre)
- Composition du jury (président, membres)
- Tableau des décisions (rang, étudiant, moyenne, crédits, décision, mention)
- Statistiques (total, admis, redoublants, etc.)
- Section de signature

### 3. Attestation (`AttestationGenerator`)

Génère une attestation de scolarité ou autre type d'attestation.

**Utilisation :**
```python
from documents.services import AttestationGenerator
from io import BytesIO

buffer = BytesIO()
generator = AttestationGenerator(etudiant, inscription, type_attestation='scolarite', buffer)
generator.generate()
```

**URL :** `/documents/attestation/<inscription_id>/<type_attestation>/`

**Types d'attestation disponibles :**
- `scolarite` : Attestation de scolarité
- Autres types personnalisables

**Contenu du document :**
- En-tête "ATTESTATION"
- Corps de l'attestation avec informations étudiant
- Date et lieu
- Section de signature

## Modèles de Données

### TypeDocumentGenere
Représente un type de document générable (relevé, PV, attestation, etc.)

### DocumentGenere
Enregistre chaque document PDF généré avec :
- Type de document
- Étudiant concerné (si applicable)
- Session/Délibération
- Fichier PDF
- Date de génération
- Utilisateur qui a généré

## Exemples d'Intégration dans les Vues

### Depuis une vue Django

```python
from django.http import HttpResponse
from documents.services import ReleveNotesGenerator
from io import BytesIO

def download_releve(request, etudiant_id, session_id):
    etudiant = Student.objects.get(id=etudiant_id)
    session = Session.objects.get(id=session_id)
    
    buffer = BytesIO()
    generator = ReleveNotesGenerator(etudiant, session, buffer)
    generator.generate()
    
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="releve_{etudiant.numero_etudiant}.pdf"'
    return response
```

### Depuis l'Admin Django

Les documents générés sont automatiquement enregistrés dans la base de données et accessibles via l'interface d'administration.

## Personnalisation

### Styles PDF

Les styles sont définis dans la classe `PDFGenerator._setup_styles()`. Vous pouvez les personnaliser selon vos besoins.

### Mise en page

Chaque générateur peut être personnalisé en modifiant :
- Les marges (`rightMargin`, `leftMargin`, etc.)
- Les largeurs de colonnes dans les tableaux
- Les couleurs et styles

### Ajout de nouveaux types de documents

1. Créer une nouvelle classe héritant de `PDFGenerator`
2. Implémenter la méthode `generate()`
3. Créer les méthodes `_build_*()` pour chaque section
4. Ajouter une vue dans `views.py`
5. Ajouter l'URL dans `urls.py`

## Notes Techniques

- Format de page : A4
- Encodage : UTF-8
- Les tableaux utilisent ReportLab `Table` avec styles personnalisés
- Les textes avec formatage utilisent `Paragraph` pour supporter le HTML
- Les documents sont générés en mémoire (BytesIO) pour de meilleures performances

## Dépendances

- `reportlab` : Génération PDF
- `Pillow` : Traitement d'images (si nécessaire pour logos, photos, etc.)
