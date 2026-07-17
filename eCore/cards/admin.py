from django.contrib import admin
from .models import Card, Category, Position, CardSettings, Personnel

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'position', 'matricule', 'created_at')
    search_fields = ('last_name', 'first_name', 'matricule', 'position__name')
    list_filter = ('category', 'education_level')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('get_last_name', 'get_first_name', 'get_position', 'get_matricule', 'issue_date', 'created_at')
    search_fields = ('personnel__last_name', 'personnel__first_name', 'personnel__matricule', 'personnel__position__name')
    readonly_fields = ('created_at', 'updated_at')

    def get_last_name(self, obj):
        return obj.personnel.last_name
    get_last_name.short_description = 'Nom'

    def get_first_name(self, obj):
        return obj.personnel.first_name
    get_first_name.short_description = 'Prénom'

    def get_position(self, obj):
        return obj.personnel.position
    get_position.short_description = 'Poste / Fonction'

    def get_matricule(self, obj):
        return obj.personnel.matricule
    get_matricule.short_description = 'Matricule'

@admin.register(CardSettings)
class CardSettingsAdmin(admin.ModelAdmin):
    pass
