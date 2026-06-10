from django.shortcuts import redirect
from django.views import View


class DepartmentAdminHomeView(View):
    def get(self, request, *args, **kwargs):
        return redirect('dashboard')

# Create your views here.
