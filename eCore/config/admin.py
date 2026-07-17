from django.contrib import admin
from .models import ConfigurationGenerale


@admin.register(ConfigurationGenerale)
class ConfigurationGeneraleAdmin(admin.ModelAdmin):
    list_display = ['nom_universite', 'email', 'telephone']
