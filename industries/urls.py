from django.urls import path

from industries.views import IndustryCreateView, IndustryDeleteView, IndustryEditView, IndustryListView

app_name = 'industries'

urlpatterns = [
    path('', IndustryListView.as_view(), name='list'),
    path('create/', IndustryCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', IndustryEditView.as_view(), name='edit'),
    path('<int:pk>/delete/', IndustryDeleteView.as_view(), name='delete'),
]
