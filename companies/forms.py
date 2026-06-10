from django import forms

from companies.models import Company, WorkPracticeTest, WorkPracticeTestQuestion


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


class WorkPracticeTestForm(forms.ModelForm):
    class Meta:
        model = WorkPracticeTest
        fields = ['name', 'duration', 'attempts_allowed', 'questions_count', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full h-[52px] px-4 rounded-[14px] border border-slate-200 bg-white text-slate-900 text-[15px] placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 transition-all duration-200 hover:border-slate-300 outline-none shadow-sm', 'placeholder': 'Masalan: Mehnat muhofazasi asoslari'}),
            'duration': forms.NumberInput(attrs={'class': 'w-full h-[52px] px-4 rounded-[14px] border border-slate-200 bg-white text-slate-900 text-[15px] placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 transition-all duration-200 hover:border-slate-300 outline-none shadow-sm', 'min': 1}),
            'attempts_allowed': forms.NumberInput(attrs={'class': 'w-full h-[52px] px-4 rounded-[14px] border border-slate-200 bg-white text-slate-900 text-[15px] placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 transition-all duration-200 hover:border-slate-300 outline-none shadow-sm', 'min': 1}),
            'questions_count': forms.NumberInput(attrs={'class': 'w-full h-[52px] px-4 rounded-[14px] border border-slate-200 bg-white text-slate-900 text-[15px] placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 transition-all duration-200 hover:border-slate-300 outline-none shadow-sm', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'peer sr-only'}),
        }


class WorkPracticeTestQuestionForm(forms.ModelForm):
    class Meta:
        model = WorkPracticeTestQuestion
        fields = ['text', 'option_1', 'option_2', 'option_3', 'correct_option']
        widgets = {
            'text': forms.Textarea(attrs={'style': 'display:none'}),
            'option_1': forms.TextInput(attrs={'class': 'v-input', 'placeholder': 'A-variant matnini kiriting'}),
            'option_2': forms.TextInput(attrs={'class': 'v-input', 'placeholder': 'B-variant matnini kiriting'}),
            'option_3': forms.TextInput(attrs={'class': 'v-input', 'placeholder': 'C-variant matnini kiriting'}),
            'correct_option': forms.RadioSelect(attrs={'style': 'display:none'}),
        }
