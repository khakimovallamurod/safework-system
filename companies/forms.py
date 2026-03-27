from django import forms

from companies.models import Company


class CompanyCreateForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['company_name', 'industry']
        widgets = {
            'company_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Kompaniya nomini kiriting',
                }
            ),
            'industry': forms.Select(attrs={'class': 'form-select'}),
        }
