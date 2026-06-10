from django.urls import path

from super_admin.views import SuperAdminHomeView

app_name = 'super_admin'

urlpatterns = [
    path('', SuperAdminHomeView.as_view(), name='home'),
]
