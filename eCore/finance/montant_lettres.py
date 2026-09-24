"""Montant en toutes lettres, en français, pour le reçu de paiement."""
from decimal import Decimal, ROUND_HALF_UP

_UNITES = (
    'zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf',
    'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
)
_DIZAINES = ('', '', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante')


def _moins_de_cent(n: int) -> str:
    if n < 17:
        return _UNITES[n]
    if n < 20:
        return 'dix-' + _UNITES[n - 10]
    dizaine, unite = divmod(n, 10)
    if dizaine == 7:
        if unite == 1:
            return 'soixante et onze'
        return 'soixante-' + _moins_de_cent(10 + unite)
    if dizaine == 8:
        if unite == 0:
            return 'quatre-vingts'
        return 'quatre-vingt-' + _UNITES[unite]
    if dizaine == 9:
        return 'quatre-vingt-' + _moins_de_cent(10 + unite)
    nom = _DIZAINES[dizaine]
    if unite == 0:
        return nom
    if unite == 1:
        return f'{nom} et un'
    return f'{nom}-{_UNITES[unite]}'


def _moins_de_mille(n: int) -> str:
    if n == 0:
        return ''
    centaines, reste = divmod(n, 100)
    morceaux = []
    if centaines == 1:
        morceaux.append('cent')
    elif centaines:
        pluriel = 's' if reste == 0 else ''
        morceaux.append(f'{_moins_de_cent(centaines)} cent{pluriel}')
    if reste:
        morceaux.append(_moins_de_cent(reste))
    return ' '.join(morceaux)


def entier_en_lettres(n: int) -> str:
    if n == 0:
        return 'zéro'
    if n < 0:
        return 'moins ' + entier_en_lettres(-n)
    morceaux = []
    milliards, n = divmod(n, 1_000_000_000)
    millions, n = divmod(n, 1_000_000)
    milliers, reste = divmod(n, 1000)
    if milliards:
        morceaux.append('un milliard' if milliards == 1 else f'{_moins_de_mille(milliards)} milliards')
    if millions:
        morceaux.append('un million' if millions == 1 else f'{_moins_de_mille(millions)} millions')
    if milliers:
        morceaux.append('mille' if milliers == 1 else f'{_moins_de_mille(milliers)} mille')
    if reste:
        morceaux.append(_moins_de_mille(reste))
    return ' '.join(morceaux)


def montant_en_lettres(montant, devise: str) -> str:
    valeur = Decimal(montant).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    entier = int(valeur)
    centimes = int((valeur - entier) * 100)
    if devise == 'CDF':
        if entier == 1 and centimes == 0:
            return 'un franc congolais'
        return f'{entier_en_lettres(entier)} francs congolais'
    libelle = 'dollar américain' if entier == 1 else 'dollars américains'
    texte = f'{entier_en_lettres(entier)} {libelle}'
    if centimes:
        cents = 'cent' if centimes == 1 else 'cents'
        texte += f' et {entier_en_lettres(centimes)} {cents}'
    return texte
