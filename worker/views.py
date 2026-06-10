from django.shortcuts import redirect
from django.views import View


class WorkerHomeView(View):
    def get(self, request, *args, **kwargs):
        return redirect('dashboard')

# Create your views here.
