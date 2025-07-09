from django import forms
from .models import Payslip

class PayslipForm(forms.ModelForm):
    gross_salary = forms.DecimalField(max_digits=10, decimal_places=2, required=True)

    class Meta:
        model = Payslip
        fields = ['employee', 'pay_period_start', 'pay_period_end']