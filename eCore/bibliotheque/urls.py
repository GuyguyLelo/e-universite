from django.urls import path

from . import views

app_name = 'bibliotheque'

urlpatterns = [
    path('', views.bibliotheque_accueil, name='accueil'),
]
