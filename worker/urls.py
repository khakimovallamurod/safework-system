from django.urls import path

from worker.views import WorkerHomeView

app_name = 'worker'

urlpatterns = [
    path('', WorkerHomeView.as_view(), name='home'),
]
