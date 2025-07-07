from django.contrib import admin
from .models import *


# Register your models here.
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('fname', 'sname', 'employee_ID', 'job_title', 'date_joined')
    search_fields = ('fname', 'job_title', 'employment_status')
    list_filter = ('job_title', 'employee_profession', 'gender', 'nationality')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('dpt_name', 'code', 'email')
    search_fields = ('dpt_name', 'code', 'email')
    list_filter = ('dpt_name', 'code', 'email')


@admin.register(JobPosition)
class JobPositionAdmin(admin.ModelAdmin):
    list_display = ('job_title', 'job_department', 'job_salary_range')
    search_fields = ('job_title', 'job_department', 'job_salary_range')
    list_filter = ('job_title', 'job_department', 'job_salary_range')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('attendance_employee', 'attendance_date', 'attendance_status')
    search_fields = ('attendance_employee', 'attendance_date', 'attendance_status')
    list_filter = ('attendance_employee', 'attendance_date', 'attendance_status')



@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('leave_employee', 'leave_type', 'leave_status')
    search_fields = ('leave_employee', 'leave_type', 'leave_status')
    list_filter = ('leave_employee', 'leave_type', 'leave_status')


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = ('performance_employee', 'performance_reviewer', 'performance_rating')
    search_fields = ('performance_employee', 'performance_reviewer', 'performance_rating')
    list_filter = ('performance_employee', 'performance_reviewer', 'performance_rating')


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('payroll_employee', 'payroll_date', 'payroll_paid_status')
    search_fields = ('payroll_employee', 'payroll_date', 'payroll_paid_status')
    list_filter = ('payroll_employee', 'payroll_date', 'payroll_paid_status')


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('training_title', 'training_trainer', 'training_date')
    search_fields = ('training_title', 'training_trainer', 'training_date')
    list_filter = ('training_title', 'training_trainer', 'training_date')

