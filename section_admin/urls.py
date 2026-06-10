from django.urls import path

from section_admin.views import SectionAdminHomeView

app_name = 'section_admin'

urlpatterns = [
    path('', SectionAdminHomeView.as_view(), name='home'),
]
