from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def bibliotheque_accueil(request):
    """Point d'entrée du module bibliothèque numérique."""
    return render(request, 'bibliotheque/bibliotheque_accueil.html')
