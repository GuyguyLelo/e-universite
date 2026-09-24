"""Barème UNIKIN 2025-2026, toutes facultés.

Sources :
- frais d'inscription : communiqué du Secrétariat général académique,
  inscriptions 2025-2026 (145 000 CDF) ;
- frais académiques : barème publié par l'Université de Kinshasa pour 2025-2026
  (350 USD en recrutement, 300 USD en classes montantes dont 200 puis 100,
  majoration de 10 % pour les étudiants étrangers).
"""

MOTIFS_UNIKIN_2025 = (
    {
        'contexte': 'frais_inscription',
        'code': 'INSCR',
        'nom': "Frais d'inscription",
        'montant': '145000',
        'devise': 'CDF',
        'ordre': 10,
        'description': (
            "Inscriptions ordinaires 2025-2026, toutes facultés. "
            "145 000 CDF à la Rawbank, à Equity BCDC ou à Access Bank."
        ),
    },
    {
        'contexte': 'acad_recrutement',
        'code': 'ACAD-REC',
        'nom': 'Frais académiques — classes de recrutement',
        'montant': '350',
        'devise': 'USD',
        'ordre': 20,
        'description': 'Année 2025-2026, tranche unique, toutes facultés.',
    },
    {
        'contexte': 'acad_montantes_1',
        'code': 'ACAD-M1',
        'nom': 'Frais académiques — classes montantes, 1re tranche',
        'montant': '200',
        'devise': 'USD',
        'ordre': 21,
        'description': 'Année 2025-2026. Première tranche des 300 USD.',
    },
    {
        'contexte': 'acad_montantes_2',
        'code': 'ACAD-M2',
        'nom': 'Frais académiques — classes montantes, 2e tranche',
        'montant': '100',
        'devise': 'USD',
        'ordre': 22,
        'description': 'Année 2025-2026. Deuxième tranche des 300 USD.',
    },
    {
        'contexte': 'acad_etranger_rec',
        'code': 'ACAD-EREC',
        'nom': 'Frais académiques étrangers — recrutement',
        'montant': '385',
        'devise': 'USD',
        'ordre': 30,
        'description': 'Majoration de 10 % sur les 350 USD des classes de recrutement.',
    },
    {
        'contexte': 'acad_etranger_1',
        'code': 'ACAD-E1',
        'nom': 'Frais académiques étrangers — 1re tranche',
        'montant': '220',
        'devise': 'USD',
        'ordre': 31,
        'description': 'Majoration de 10 % sur la première tranche des classes montantes.',
    },
    {
        'contexte': 'acad_etranger_2',
        'code': 'ACAD-E2',
        'nom': 'Frais académiques étrangers — 2e tranche',
        'montant': '110',
        'devise': 'USD',
        'ordre': 32,
        'description': 'Majoration de 10 % sur la deuxième tranche des classes montantes.',
    },
)
