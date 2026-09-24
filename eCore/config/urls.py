from django.urls import path

from . import views

app_name = 'config'

urlpatterns = [
    path('', views.etablissement_list, name='etablissement_list'),
    path('nouveau/', views.etablissement_create, name='etablissement_create'),
    path('<int:pk>/modifier/', views.etablissement_update, name='etablissement_update'),
    path('<int:pk>/supprimer/', views.etablissement_delete, name='etablissement_delete'),
]
