from django import forms

from professions.models import Profession


class ProfessionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['nizom_file'].required = True
        self.fields['nizom_file'].widget.attrs.update({'class': 'form-control', 'accept': '.pdf,.docx'})

    class Meta:
        model = Profession
        fields = ['name', 'nizom_file', 'start_time', 'active_until']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kasb turi nomi'}),
            'start_time': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'active_until': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        active_until = cleaned.get('active_until')
        if start and active_until and active_until <= start:
            raise forms.ValidationError("Faollik tugashi boshlanish sanasidan keyin bo‘lishi kerak.")
        return cleaned
