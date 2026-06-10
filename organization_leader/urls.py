from django.urls import path

from organization_leader.views import OrganizationLeaderHomeView

app_name = 'organization_leader'

urlpatterns = [
    path('', OrganizationLeaderHomeView.as_view(), name='home'),
]
