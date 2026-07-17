from django.contrib import admin

from .models import BaremePrestation, EnveloppeBudgetaire, Horaire, HoraireLigne, PaieMensuelle, PersonnelBaremeInitial


@admin.register(EnveloppeBudgetaire)
class EnveloppeBudgetaireAdmin(admin.ModelAdmin):
    list_display = ("annee", "mois", "montant", "created_at")
    list_filter = ("annee", "mois")
    ordering = ("-annee", "-mois")


@admin.register(PaieMensuelle)
class PaieMensuelleAdmin(admin.ModelAdmin):
    list_display = ("enveloppe", "montant_total_valide", "validee_le", "valide_par")
    list_filter = ("validee_le",)
    readonly_fields = ("validee_le",)


@admin.register(PersonnelBaremeInitial)
class PersonnelBaremeInitialAdmin(admin.ModelAdmin):
    list_display = ("personnel", "bareme", "quantite", "created_at")
    list_filter = ("bareme__categorie",)
    search_fields = ("personnel__last_name", "personnel__first_name", "bareme__intitule")

@admin.register(BaremePrestation)
class BaremePrestationAdmin(admin.ModelAdmin):
    list_display = ("intitule", "categorie", "periode", "montant", "active", "ordre")
    list_filter = ("categorie", "periode", "active")
    search_fields = ("intitule",)
    ordering = ("categorie", "ordre", "intitule")


class HoraireLigneInline(admin.TabularInline):
    model = HoraireLigne
    extra = 0


@admin.register(Horaire)
class HoraireAdmin(admin.ModelAdmin):
    list_display = ("titre", "classe", "annee_academique", "semestre", "active", "created_at")
    list_filter = ("active", "annee_academique", "semestre", "classe")
    search_fields = ("titre", "classe__code", "classe__promotion__code")
    inlines = [HoraireLigneInline]


@admin.register(HoraireLigne)
class HoraireLigneAdmin(admin.ModelAdmin):
    list_display = ("horaire", "jour", "heure_debut", "heure_fin", "code_affichage", "local_affichage", "titulaire_affichage")
    list_filter = ("jour", "horaire__annee_academique", "horaire__semestre")
    search_fields = ("ue_code", "element_constitutif__code", "professeur__first_name", "professeur__last_name")
