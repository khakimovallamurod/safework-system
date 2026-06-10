from django import forms

from professions.models import Profession


class ProfessionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['nizom_file'].required = True
        self.fields['nizom_file'].widget.attrs.update({'class': 'form-control', 'accept': 'application/pdf'})

    class Meta:
        model = Profession
        fields = ['name', 'nizom_file']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kasb turi nomi'}),
        }
