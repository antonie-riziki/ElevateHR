from django.urls import path, include
from . import views
from django.contrib.auth.views import LoginView,LogoutView
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('home', views.index, name='home'),
    path('', views.hr_registration, name='hr-registration'),
    path('login/', views.login, name='login'),
    path('employees/', views.employees, name='employees'),
    path('recruitment/', views.recruitment, name='recruitment')
]