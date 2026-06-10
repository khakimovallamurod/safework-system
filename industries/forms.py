from django import forms

from industries.models import Industry


class IndustryCreateForm(forms.ModelForm):
    class Meta:
        model = Industry
        fields = ['name']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': "Soha nomini kiriting",
                }
            )
        }
