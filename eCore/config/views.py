from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EtablissementForm
from .models import Etablissement


@login_required
def etablissement_list(request):
    qs = Etablissement.objects.all()
    statut = request.GET.get('statut')
    if statut in dict(Etablissement.STATUT_CHOICES):
        qs = qs.filter(statut_juridique=statut)
    paginator = Paginator(qs, 15)
    etablissements = paginator.get_page(request.GET.get('page'))
    return render(request, 'config/etablissement_list.html', {
        'etablissements': etablissements,
        'statut': statut or '',
        'pilote': Etablissement.get_pilote(),
    })


@login_required
def etablissement_create(request):
    if request.method == 'POST':
        form = EtablissementForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Établissement enregistré.')
            return redirect('config:etablissement_list')
    else:
        form = EtablissementForm()
    return render(request, 'config/etablissement_form.html', {
        'form': form,
        'title': 'Nouvel établissement',
    })


@login_required
def etablissement_update(request, pk):
    etablissement = get_object_or_404(Etablissement, pk=pk)
    if request.method == 'POST':
        form = EtablissementForm(request.POST, request.FILES, instance=etablissement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Établissement modifié.')
            return redirect('config:etablissement_list')
    else:
        form = EtablissementForm(instance=etablissement)
    return render(request, 'config/etablissement_form.html', {
        'form': form,
        'title': 'Modifier l’établissement',
        'object': etablissement,
    })


@login_required
def etablissement_delete(request, pk):
    etablissement = get_object_or_404(Etablissement, pk=pk)
    if request.method == 'POST':
        try:
            etablissement.delete()
        except ProtectedError:
            messages.error(
                request,
                'Cet établissement a déjà des sections ou des étudiants. Retirez-les avant de le supprimer.',
            )
            return redirect('config:etablissement_list')
        messages.success(request, 'Établissement supprimé.')
        return redirect('config:etablissement_list')
    return render(request, 'config/etablissement_confirm_delete.html', {
        'etablissement': etablissement,
    })
