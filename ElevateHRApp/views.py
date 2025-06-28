from django.shortcuts import render

# Create your views here.

def hr_registration(request):
    return render(request, 'hr_registration.html')

def login(request):
    return render(request, 'login.html')

def index(request):
    return render(request, 'index.html')

def employees(request):
    return render(request, 'employees.html')

def recruitment(request):
    return render(request, 'recruitment.html')