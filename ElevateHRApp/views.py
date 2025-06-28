from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'index.html')


def employees(request):
    return render(request, 'employees.html')

def recruitment(request):
    return render(request, 'recruitment.html')