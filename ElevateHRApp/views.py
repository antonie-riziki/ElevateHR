
from .forms import PayslipForm
from .models import *
from uuid import UUID
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
import africastalking
import os
import sys
import secrets
import string
import json
import shutil
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(1, './ElevateHRApp')

from rag_model import get_qa_chain, query_system
from image_generation import google_image_generator

# Initialize Africa's Talking and Google Generative AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
africastalking.initialize(
    username="EMID",
    api_key=os.getenv("AT_API_KEY")
)

sms = africastalking.SMS
airtime = africastalking.Airtime
voice = africastalking.Voice

otp_storage = {}


# Custom modules

def generate_otp(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def send_otp(phone_number, otp_sms):

    recipients = [f"+254{str(phone_number)}"]

    # Set your message
    message = f"{otp_sms}"

    # Set your shortCode or senderId
    sender = 20880

    try:
        response = sms.send(message, recipients, sender)

        print(response)

    except Exception as e:
        print(f'Houston, we have a problem: {e}')


def welcome_message(first_name, phone_number):

    recipients = [f"+254{str(phone_number)}"]

    # Set your message
    message = f"{first_name}, Welcome to ElevateHR! Your account is now active. Lets streamline HR tasks together."

    # Set your shortCode or senderId
    sender = 20880

    try:
        response = sms.send(message, recipients, sender)

        print(response)

    except Exception as e:
        print(f'Houston, we have a problem: {e}')


def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-2.0-flash",

        system_instruction=f"""

        You are ElevateHR — a helpful, professional, and smart HR assistant. 
        You support employees, managers, and HR staff with information on recruitment, onboarding, employee wellness, leave policies, performance management, and workplace culture.

        Guidelines:
        - Use a warm, clear, and professional tone.
        - Keep answers short and relevant (2–4 sentences max).
        - If unsure or a question is out of scope, recommend contacting HR directly.
        - Avoid making assumptions about company-specific policies unless provided.
        - Be friendly but not too casual. Respectful and informative.

        Example Output:
        - "Hi there! You can apply for leave through the Employee Portal under 'My Requests'. Need help navigating it?"
        - "Sure! During onboarding, you’ll get access to all core HR systems and meet your assigned buddy."
        
        Donts:
        - Don't provide personal opinions or unverified information.
        - Don't discuss sensitive topics like salary negotiations or personal grievances.
        - Don't use jargon or overly technical language.
        - Don't make assumptions about the user's knowledge or experience level.
        - Don't provide legal or financial advice.
        - Don't engage in casual conversation unrelated to HR, Employee, Managerial, Employer or Work Environment topics.
        
        """)

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=1000,
            temperature=1.5,
        )

    )

    return response.text


@csrf_exempt  # remove this in production, use CSRF token
def process_candidates(request):
    if request.method == 'POST':
        prompt = request.POST.get('prompt', '')

        # Create a temp directory
        temp_dir = tempfile.mkdtemp()

        try:
            # Save uploaded files to temp_dir
            for file in request.FILES.getlist('files'):
                fs = FileSystemStorage(location=temp_dir)
                fs.save(file.name, file)

            # Get QA chain and run query
            qa_chain = get_qa_chain(temp_dir)
            result = query_system(prompt, qa_chain)

            # Return result as HTML or Markdown
            # or text/markdown
            return HttpResponse(result, content_type='text/html')
        except Exception as e:
            return HttpResponse(f"<strong>Error:</strong> {str(e)}", status=500)
        finally:
            # Clean up temp files
            shutil.rmtree(temp_dir, ignore_errors=True)
    return HttpResponse("Invalid request method.", status=400)


# Create your views here.

def hr_registration(request):
    return render(request, 'hr_registration.html')


@csrf_exempt
def send_otp_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        first_name = request.POST.get('firstName')
        last_name = request.POST.get('lastName')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')

        if password != confirm_password:
            return JsonResponse({'error': 'Passwords do not match'}, status=400)

        otp_code = generate_otp()
        otp_storage[phone] = {
            'otp': otp_code,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,
        }

        welcome_message(first_name, phone)

        send_otp(phone, otp_code)

        # if get_otp_code:
        #     welcome_message(first_name, phone)

        return JsonResponse({'status': 'OTP sent', 'phone': phone})

    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def verify_otp_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        entered_otp = request.POST.get('otp')
        first_name = request.POST.get('first_name')
        saved = otp_storage.get(phone)

        if saved and saved['otp'] == entered_otp:
            welcome_message(first_name, phone)
            messages.success(
                request, "Registration successful! Welcome to ElevateHR.")
            return redirect('home')  # or your actual home page
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'verify_otp.html', {'phone': phone, 'first_name': first_name})
    return redirect('hr_registration')


@csrf_exempt
def chatbot_response(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message', '')

        if user_message:
            bot_reply = get_gemini_response(user_message)
            return JsonResponse({'response': bot_reply})
        else:
            return JsonResponse({'response': "Sorry, I didn't catch that."}, status=400)


def login(request):
    return render(request, 'login.html')


def index(request):
    return render(request, 'index.html')


def employees(request):
    emp = Employee.objects.all()
    context = {
        'employees': emp,
    }
    return render(request, 'employees.html', context)


def employee_dashboard(request, employee_ID):
    emp_dash = get_object_or_404(Employee, employee_ID=employee_ID)
    context = {
        'emp_dash': emp_dash,
    }
    return render(request, 'employee-dashboard.html', context)

@csrf_exempt
def campaign(request):
    if request.method == 'POST':
        campaign_data = {
            "job_title": request.POST.get("jobTitle"),
            "level": request.POST.get("level"),
            "experience": request.POST.get("experience"),
            "salary_range": request.POST.get("salaryRange"),
            "description": request.POST.get("description"),
            "requirements": request.POST.get("requirements"),
            "contact_email": request.POST.get("email"),
            "company_website": request.POST.get("website"),
        }

        # Generate prompt string from campaign data
        prompt = f"""
        Create a poster for the position of {campaign_data['job_title']} at {campaign_data['company_website']}.
        Level: {campaign_data['level']}, Experience: {campaign_data['experience']}, Salary: {campaign_data['salary_range']}.
        Description: {campaign_data['description']}.
        Requirements: {campaign_data['requirements']}.
        """

        # Call your image generator
        generated_image = google_image_generator(prompt)

        return render(request, 'campaign.html', {
            "campaign": campaign_data,
            "generated_image": generated_image,
        })
    return render(request, 'campaign.html')


def job_posting(request):
    return render(request, 'job_posting.html')


def recruitment(request):
    return render(request, 'recruitment.html')


def time_attendance(request):
    return render(request, 'time_attendance.html')


def leave_management(request):
    return render(request, 'leave_management.html')


def reporting_analytics(request):
    return render(request, 'reporting_analytics.html')


def performance(request):
    return render(request, 'performance.html')


def performance_management(request):
    return render(request, 'performance.html')


def payslip_list(request):
    payslips = Payslip.objects.select_related('employee').all()
    employees = Employee.objects.all()
    context = {
        'payslips': payslips,
        'employees': employees
    }
    return render(request, 'payslip_list.html', context)


@require_POST
def generate_payslip(request):
    form = PayslipForm(request.POST)
    if form.is_valid():
        payslip = form.save(commit=False)
        payslip.gross_salary = form.cleaned_data['gross_salary']
        payslip.save()
        return JsonResponse({
            'success': True,
            'message': 'Payslip generated successfully.',
            'payslip': {
                'id': payslip.id,
                'employee': f"{payslip.employee.fname} {payslip.employee.lname}",
                'department': str(payslip.employee.department) if payslip.employee.department else "",
                'position': payslip.employee.employee_profession,
                'status': payslip.employee.employment_status,
                'pay_period_start': payslip.pay_period_start.strftime('%b %d, %Y'),
                'pay_period_end': payslip.pay_period_end.strftime('%b %d, %Y'),
                'gross_salary': float(payslip.gross_salary),
                'total_deductions': float(getattr(payslip, 'total_deductions', 0)),
                'net_salary': float(getattr(payslip, 'net_salary', 0)),
                'payslip_status': payslip.status,
            }
        })
    else:
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
