import random
from datetime import timedelta, datetime, date
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


@csrf_exempt
def index(request):
    if request.method == 'POST':
        session_id = request.POST.get('sessionId')
        session_code = request.POST.get('serviceCode')
        phone_number = request.POST.get('phoneNumber')
        text = request.POST.get('text')

        response = ""

        if text == "":
            response = "CON Welcome to ElevateHR \n"
            response += "1. Clock In/Out \n"
            response += "2. Report Status \n"
            response += "3. Request Leave \n"
            response += "4. Performance Summary \n"
            respone += "5. Payment Summary \n"
            response += "6. Download Docs \n"

        elif text == "1":
            response = "CON Select an option: \n"
            response += "1. Clock In \n"
            response += "2. Clock Out \n"

        elif text == "1*1":
            response = "END You have successfully clocked in. Have a good day ahead"

        elif text == "1*2":
            response = "END You have successfully clocked out. Kwaheri!"

        elif text == "2":
            response = "END Log in to your profile for a detailed report"

        elif text == "3":
            response = "END Your leave is pending review"

        elif text == "4":
            response = """
            END You have had an average performance. \n
            For the full report, find it on your profile
            """

        elif text == "5":
            response = """
            END Your payment summary is ready.\n
            Login to your profile to read the full summary
            """

        elif text == "6":
            response = """
            END The Documents are ready. \n 
            Visit your profile to download
            """

        return HttpResponse(response)
