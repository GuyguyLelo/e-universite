"""
URL configuration for gestacademia project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('frontapp.urls')),
    path('login/', RedirectView.as_view(pattern_name='login', permanent=False), name='login_short'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('admin/', admin.site.urls),
    path('documents/', include('documents.urls')),
    path('academics/', include('academics.urls')),
    path('students/', include('students.urls')),
    path('evaluations/', include('evaluations.urls')),
    path('deliberations/', include('deliberations.urls')),
    path('cards/', include('cards.urls')),
    path('prestation/', include('prestation.urls')),
    path('finance/', include('finance.urls')),
    path('projets/', include('projets.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
