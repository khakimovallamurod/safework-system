from django.urls import path

from companies.views import CompanyCreateView, CompanyDeleteView, CompanyEditView, CompanyListView

app_name = 'companies'

urlpatterns = [
    path('', CompanyListView.as_view(), name='list'),
    path('create/', CompanyCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', CompanyEditView.as_view(), name='edit'),
    path('<int:pk>/delete/', CompanyDeleteView.as_view(), name='delete'),
]
