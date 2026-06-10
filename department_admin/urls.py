from django.urls import path

from department_admin.views import DepartmentAdminHomeView

app_name = 'department_admin'

urlpatterns = [
    path('', DepartmentAdminHomeView.as_view(), name='home'),
]
