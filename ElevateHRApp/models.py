from django.db import models
from django.utils.text import slugify
from django.utils import timezone
import uuid


# Create your models here.
class Department(models.Model):
    DEPT = [
        ('Sales', 'Sales'),
        ('Marketing', 'Marketing'),
        ('Human Resources', 'Human Resources'),
        ('Finance', 'Finance'),
        ('Information Technology', 'Information Technology'),
        ('Operations', 'Operations'),
        ('Customer Service', 'Customer Service'),
        ('Legal', 'Legal'),
        ('Procurement', 'Procurement'),
        ('Research and Development', 'Research and Development'),
        ('Logistics', 'Logistics'),
        ('Administration', 'Administration'),
        ('Engineering', 'Engineering'),
        ('Production', 'Production'),
        ('Quality Assurance', 'Quality Assurance'),
        ('Business Development', 'Business Development'),
        ('Public Relations', 'Public Relations'),
        ('Training and Development', 'Training and Development'),
        ('Security', 'Security'),
        ('Compliance', 'Compliance')
    ]

    dpt_name = models.CharField(max_length=200, choices=DEPT)
    code = models.CharField(max_length=20, unique=True)
    incharge = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments'
    )
    # location = models.CharField(max_length=100, blank=True, null=True)
    extension_number = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['dpt_name']

    def __str__(self):
        return self.dpt_name

class Employee(models.Model):
    PROFESSIONS = [
        ('Accountant', 'Accountant'),
        ('Architect', 'Architect'),
        ('Artist', 'Artist'),
        ('Chef', 'Chef'),
        ('Consultant', 'Consultant'),
        ('Data Analyst', 'Data Analyst'),
        ('Data Scientist', 'Data Scientist'),
        ('Dentist', 'Dentist'),
        ('Developer', 'Developer'),
        ('Doctor', 'Doctor'),
        ('Engineer', 'Engineer'),
        ('Financial Analyst', 'Financial Analyst'),
        ('Graphic Designer', 'Graphic Designer'),
        ('HR Manager', 'HR Manager'),
        ('Journalist', 'Journalist'),
        ('Lawyer', 'Lawyer'),
        ('Lecturer', 'Lecturer'),
        ('Manager', 'Manager'),
        ('Marketing Specialist', 'Marketing Specialist'),
        ('Mechanic', 'Mechanic'),
        ('Nurse', 'Nurse'),
        ('Pharmacist', 'Pharmacist'),
        ('Photographer', 'Photographer'),
        ('Pilot', 'Pilot'),
        ('Product Manager', 'Product Manager'),
        ('Project Manager', 'Project Manager'),
        ('Psychologist', 'Psychologist'),
        ('Sales Executive', 'Sales Executive'),
        ('Senior Engineer', 'Senior Engineer'),
        ('Software Engineer', 'Software Engineer'),
        ('Teacher', 'Teacher'),
        ('UX Designer', 'UX Designer'),
        ('Veterinarian', 'Veterinarian'),
        ('Web Developer', 'Web Developer'),
        ('Writer', 'Writer')
    ]

    MARITAL = [
        ('Single', 'Single'),
        ('Married', 'Married'),
        ('Divorced', 'Divorced'),
        ('Widowed', 'Widowed')
    ]

    CURRENT_NATIONALITY = [
        ('Kenya', 'Kenya'),
    ]

    EMP_TYPE = [
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Contract', 'Contract'),
        ('Intern', 'Intern')
    ]

    EMP_STATUS = [
        ('Active', 'Active'),
        ('On Leave', 'On Leave'),
        ('Terminated', 'Terminated'),
        ('Resigned', 'Resigned'),
        ('Retired', 'Retired')
    ]

    fname = models.CharField('First Name', max_length=200)
    lname = models.CharField('Last Name', max_length=200)
    sname = models.CharField('Surname', max_length=200)
    employee_dob = models.DateTimeField(auto_now_add=True)
    employee_phonenumber = models.IntegerField(default=0, null=False, help_text='contributors personal phone number')
    employee_profession = models.CharField(null=False, choices=PROFESSIONS, help_text='Career or professional designation')
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    marital_status = models.CharField(max_length=20, choices=MARITAL)
    nationality = models.CharField(max_length=50, choices=CURRENT_NATIONALITY)

    # Contact Details
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=10, blank=True, null=True)

    # Job Details
    employee_ID = models.CharField(primary_key=True, default=uuid.uuid4, max_length=100, editable=False, unique=True, blank=True)
    job_title = models.CharField(max_length=100)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    employment_type = models.CharField(max_length=50, choices=EMP_TYPE)
    date_joined = models.DateField()
    probation_end_date = models.DateField(blank=True, null=True)
    employment_status = models.CharField(max_length=20, choices=EMP_STATUS, default='Active')
    supervisor = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True,
                                   related_name='subordinates')

    # Compensation
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    pay_grade = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100)
    bank_account_number = models.CharField(max_length=50)
    tax_id_number = models.CharField(max_length=50, blank=True, null=True)
    nhif_number = models.CharField(max_length=50, blank=True, null=True)
    nssf_number = models.CharField(max_length=50, blank=True, null=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_relation = models.CharField(max_length=50)
    emergency_contact_phone = models.CharField(max_length=15)

    # Documents
    id_number = models.CharField(max_length=50)
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    contract_file = models.FileField(upload_to='contracts/', blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    # System Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ['-created_at']



    def __str__(self):
        return self.fname + ' ' + self.lname + ' EHR' + self.employee_ID