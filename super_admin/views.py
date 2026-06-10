from django.shortcuts import redirect
from django.views import View


class SuperAdminHomeView(View):
    def get(self, request, *args, **kwargs):
        return redirect('dashboard')

# Create your views here.
