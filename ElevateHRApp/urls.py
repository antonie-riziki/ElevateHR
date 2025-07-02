from django.urls import path, include
from . import views
from django.contrib.auth.views import LoginView,LogoutView
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('home', views.index, name='home'),
    path('', views.hr_registration, name='hr-registration'),
    path('send-otp/', views.send_otp_view, name='send_otp'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('login/', views.login, name='login'),
    path('employees/', views.employees, name='employees'),
    path('recruitment/', views.recruitment, name='recruitment'),
    path('performance-management/', views.performance_management, name='performance-management'),
    path('job-posting/', views.job_posting, name='job-posting'),
    path('time-attendance/', views.time_attendance, name='time-attendance'),
    path('leave-management/', views.leave_management, name='leave-management'),
    path('reporting-analytics/', views.reporting_analytics, name='reporting-analytics'),
    path('chatbot-response/', views.chatbot_response_view, name='chatbot_response'),
    path('performance/', views.performance, name='performance'),
    path('process-candidates/', views.process_candidates, name='process_candidates'),
]