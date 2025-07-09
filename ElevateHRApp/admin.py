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


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
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


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'pay_period_start', 'pay_period_end', 'status', 'net_salary')
    search_fields = ('employee__fname', 'employee__lname', 'status')
    list_filter = ('status', 'pay_period_start', 'pay_period_end')
    readonly_fields = ('generated_on', 'gross_salary', 'total_deductions', 'net_salary')
    fieldsets = (
        ('Core Information', {
            'fields': ('employee', ('pay_period_start', 'pay_period_end'), 'status')
        }),
        ('Earnings', {
            'fields': ('basic_salary', 'allowances', 'bonuses', 'gross_salary')
        }),
        ('Deductions', {
            'fields': ('income_tax', 'nssf_deduction', 'nhif_deduction', 'other_deductions', 'total_deductions')
        }),
        ('Summary', {
            'fields': ('net_salary', 'generated_on')
        }),
    )

@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = ('payslip', 'status', 'disbursement_date', 'amount', 'transaction_id')
    search_fields = ('payslip__employee__fname', 'payslip__employee__lname', 'status', 'transaction_id')
    list_filter = ('status', 'disbursement_date')
    readonly_fields = ('disbursement_date',)


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('training_title', 'training_trainer', 'training_date')
    search_fields = ('training_title', 'training_trainer', 'training_date')
    list_filter = ('training_title', 'training_trainer', 'training_date')

