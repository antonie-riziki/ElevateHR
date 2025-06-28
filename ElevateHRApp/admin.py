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
