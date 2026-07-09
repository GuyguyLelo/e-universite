from django.urls import path
from .views import *

app_name = 'deliberations'

urlpatterns = [
    # Paramètres LMD
    path('parametres-lmd/', parametres_lmd_list, name='parametres_lmd_list'),
    path('parametres-lmd/nouveaux/', parametres_lmd_create, name='parametres_lmd_create'),
    path('parametres-lmd/<int:pk>/modifier/', parametres_lmd_update, name='parametres_lmd_update'),
    
    # Délibérations
    path('deliberations/', deliberation_list, name='deliberation_list'),
    path('deliberations/nouvelle/', deliberation_create, name='deliberation_create'),
    path('deliberations/<int:pk>/', deliberation_detail, name='deliberation_detail'),
    path('deliberations/<int:pk>/modifier/', deliberation_update, name='deliberation_update'),
    path('deliberations/<int:pk>/calculer/', deliberation_calculer, name='deliberation_calculer'),

    # Dettes académiques
    path('dettes/', dette_list, name='dette_list'),

    # Gestion du jury
    path('jury/', jury_gestion, name='jury_gestion'),
    
    # Décisions du jury
    path('decisions/<int:pk>/modifier/', decision_jury_update, name='decision_jury_update'),
]
