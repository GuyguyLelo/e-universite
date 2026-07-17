from django.urls import path

from . import views

app_name = 'formation_continue'

urlpatterns = [
    path('', views.accueil, name='accueil'),

    path('sessions/', views.session_list, name='session_list'),
    path('sessions/nouveau/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/modifier/', views.session_update, name='session_update'),
    path('sessions/<int:pk>/supprimer/', views.session_delete, name='session_delete'),

    path('cloture-session/', views.cloture_session_list, name='cloture_session_list'),
    path('cloture-session/<int:pk>/', views.cloture_session_detail, name='cloture_session_detail'),

    path('modules/', views.module_list, name='module_list'),
    path('modules/nouveau/', views.module_create, name='module_create'),
    path('modules/<int:pk>/modifier/', views.module_update, name='module_update'),
    path('modules/<int:pk>/supprimer/', views.module_delete, name='module_delete'),

    path('formateurs/', views.formateur_list, name='formateur_list'),
    path('formateurs/nouveau/', views.formateur_create, name='formateur_create'),
    path('formateurs/<int:pk>/modifier/', views.formateur_update, name='formateur_update'),
    path('formateurs/<int:pk>/supprimer/', views.formateur_delete, name='formateur_delete'),

    path('seminaristes/', views.seminariste_list, name='seminariste_list'),
    path('seminaristes/nouveau/', views.seminariste_create, name='seminariste_create'),
    path('seminaristes/<int:pk>/', views.seminariste_detail, name='seminariste_detail'),
    path('seminaristes/<int:pk>/modifier/', views.seminariste_update, name='seminariste_update'),
    path('seminaristes/<int:pk>/supprimer/', views.seminariste_delete, name='seminariste_delete'),

    path('offres/', views.offre_list, name='offre_list'),
    path('offres/nouveau/', views.offre_create, name='offre_create'),
    path('offres/<int:pk>/modifier/', views.offre_update, name='offre_update'),
    path('offres/<int:pk>/supprimer/', views.offre_delete, name='offre_delete'),

    path('inscriptions/', views.inscription_list, name='inscription_list'),
    path('inscriptions/nouveau/', views.inscription_create, name='inscription_create'),
    path('inscriptions/<int:pk>/modifier/', views.inscription_update, name='inscription_update'),
    path('inscriptions/<int:pk>/supprimer/', views.inscription_delete, name='inscription_delete'),

    path('presences/', views.presence_list, name='presence_list'),
    path('presences/nouveau/', views.presence_create, name='presence_create'),
    path('presences/<int:pk>/modifier/', views.presence_update, name='presence_update'),
    path('presences/<int:pk>/supprimer/', views.presence_delete, name='presence_delete'),

    path('brevets/', views.brevet_list, name='brevet_list'),
    path('brevets/nouveau/', views.brevet_create, name='brevet_create'),
    path('brevets/<int:pk>/modifier/', views.brevet_update, name='brevet_update'),
    path('brevets/<int:pk>/pdf/', views.brevet_pdf, name='brevet_pdf'),
    path('brevets/<int:pk>/supprimer/', views.brevet_delete, name='brevet_delete'),
]
