from django.urls import path

from professions.views import ProfessionCreateView, ProfessionDeleteView, ProfessionEditView, ProfessionListView

app_name = 'professions'

urlpatterns = [
    path('', ProfessionListView.as_view(), name='list'),
    path('create/', ProfessionCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', ProfessionEditView.as_view(), name='edit'),
    path('<int:pk>/delete/', ProfessionDeleteView.as_view(), name='delete'),
]
