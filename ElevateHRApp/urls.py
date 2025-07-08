from django.urls import path, include
from . import views
from django.contrib.auth.views import LoginView,LogoutView
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('home', views.index, name='home'),
    path('', views.hr_registration, name='hr-registration'),
    path('send-otp/', views.send_otp_view, name='send_otp'),
    # path('welcome-message/', views.welcome_message_view, name='welcome_message'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('login/', views.login, name='login'),
    path('employees/', views.employees, name='employees'),
    # path('employee-dasboard', views.employee_dashboard, name='employee_dashboard'),
    path('employee_dashboard/<int:employee_ID>/', views.employee_dashboard, name='employee_dashboard'),

    path('recruitment/', views.recruitment, name='recruitment'),
    path('job-posting/', views.job_posting, name='job-posting'),
    path('time-attendance/', views.time_attendance, name='time-attendance'),
    path('leave-management/', views.leave_management, name='leave-management'),
    path('reporting-analytics/', views.reporting_analytics, name='reporting-analytics'),
    path('chatbot-response/', views.chatbot_response, name='chatbot_response'),
    path('performance/', views.performance, name='performance'),
    path('process-candidates/', views.process_candidates, name='process_candidates'),
]
