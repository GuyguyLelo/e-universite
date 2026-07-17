from django.urls import path
from . import views

app_name = 'cards'

urlpatterns = [
    path('public/<uuid:public_token>/', views.public_card_profile, name='public_profile'),

    # --- Personnel URLs ---
    path('personnel/', views.PersonnelListView.as_view(), name='personnel_list'),
    path('personnel/new/', views.PersonnelCreateView.as_view(), name='personnel_create'),
    path('personnel/importer/', views.personnel_import, name='personnel_import'),
    path('personnel/<int:pk>/', views.PersonnelDetailView.as_view(), name='personnel_detail'),
    path('personnel/<int:pk>/edit/', views.PersonnelUpdateView.as_view(), name='personnel_edit'),
    path('personnel/<int:pk>/delete/', views.PersonnelDeleteView.as_view(), name='personnel_delete'),

    # --- Card URLs ---
    path('', views.CardListView.as_view(), name='card_list'),
    path('new/', views.CardCreateView.as_view(), name='card_create'),
    path('<int:pk>/', views.CardDetailView.as_view(), name='card_detail'),
    path('<int:pk>/edit/', views.CardUpdateView.as_view(), name='card_edit'),
    path('<int:pk>/delete/', views.CardDeleteView.as_view(), name='card_delete'),
    path('<int:pk>/generate/', views.generate_card, name='card_generate'),
    path('<int:pk>/pdf/', views.card_pdf, name='card_pdf'),
]
