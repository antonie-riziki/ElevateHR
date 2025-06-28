from django.urls import path, include
from . import views
from django.contrib.auth.views import LoginView,LogoutView
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('', views.index, name='home'),
    path('employees/', views.employees, name='employees'),
    path('recruitment/', views.recruitment, name='recruitment')
]