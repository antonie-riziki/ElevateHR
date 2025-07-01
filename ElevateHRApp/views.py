
import africastalking
import os
import secrets
import string
import google.generativeai as genai

from dotenv import load_dotenv

load_dotenv()


from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


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
    message = f"{otp_sms}";

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
    message = f"{first_name}, Welcome to ElevateHR! Your account is now active. Let’s streamline HR tasks together.";

    # Set your shortCode or senderId
    sender = 20880

    try:
        response = sms.send(message, recipients, sender)

        print(response)

    except Exception as e:
        print(f'Houston, we have a problem: {e}')


def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-1.5-flashs",

        system_instruction="""

            You are VaaBot — the intelligent, stylish, and witty assistant behind Vaa Smart, a smart fashion system that helps users plan, evaluate, and elevate their outfits.

            Your core functions include:
            - Suggesting daily or weekly outfit recommendations based on user inputs such as gender, body type, race, occasion, and personal style.
            - Roasting user-submitted outfits using a selected persona and roast intensity level.
            - Offering feedback, fashion tips, or drip improvements when requested.
            - Maintaining an engaging, helpful, and lightly stylish tone — intelligent, but not robotic.


            Guidelines:
            - Keep responses precise, conversational, and fashion-savvy.
            - Use Nairobi-style lingo or light local slang when appropriate (e.g., "drip", "uko freshi", "hii look inakataa").
            - Adapt tone depending on the feature in use — warm for outfit planning, cheeky for roasting, direct for improvement suggestions.
            - Never repeat instructions back to the user. Just get to the point.
            - Be culturally aware, inclusive, and expressive when referring to style, identity, or fashion norms.

            You’re not just a chatbot — you’re their digital stylist, fashion consultant, and style hype-partner.


            Example Output: 

            👕 Monday Fit:
            - Occasion: Casual Workday
            - Recommended Outfit: Light denim jacket, graphic tee, slim black jeans, white sneakers.

            """

    )

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=1000,
            temperature=1.5,
        )

    )

    return response.text



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

        send_otp(phone, otp_code)

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
            messages.success(request, "Registration successful! Welcome to ElevateHR.")
            return redirect('home')  # or your actual home page
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'verify_otp.html', {'phone': phone, 'first_name': first_name})
    return redirect('hr_registration')

def login(request):
    return render(request, 'login.html')

def index(request):
    return render(request, 'index.html')

def employees(request):
    return render(request, 'employees.html')

def recruitment(request):
    return render(request, 'recruitment.html')




