from django.contrib import admin
from .models import ConfigurationGenerale, Etablissement


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'statut_juridique', 'categorie', 'province', 'phase', 'actif']
    list_filter = ['statut_juridique', 'categorie', 'phase', 'province', 'actif']
    search_fields = ['code', 'nom', 'ville', 'numero_agrement', 'promoteur']


@admin.register(ConfigurationGenerale)
class ConfigurationGeneraleAdmin(admin.ModelAdmin):
    list_display = ['nom_universite', 'email', 'telephone']
