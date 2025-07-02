from django.urls import path, include
from . import views
from django.contrib.auth.views import LoginView,LogoutView
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('', views.index, name='home'),
    path('verify-registration/', views.hr_registration, name='hr-registration'),
    path('send-otp/', views.send_otp_view, name='send_otp'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('login/', views.login, name='login'),
    path('employees/', views.employees, name='employees'),
    path('recruitment/', views.recruitment, name='recruitment')
]
