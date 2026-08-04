from django.urls import path
from . import views

app_name = 'ppe'

urlpatterns = [
    path('', views.ppe_dashboard, name='dashboard'),
    path('type/create/', views.create_ppe_type, name='create_type'),
    path('type/list/', views.ppe_type_list, name='type_list'),
    path('type/edit/<int:pk>/', views.edit_ppe_type, name='edit_type'),
    path('type/delete/<int:pk>/', views.delete_ppe_type, name='delete_type'),
    path('issue/', views.issue_ppe, name='issue'),
    path('issue/edit/<int:pk>/', views.edit_ppe_issue, name='edit_issue'),
    path('issue/delete/<int:pk>/', views.delete_ppe_issue, name='delete_issue'),
    path('acknowledge/<int:pk>/', views.acknowledge_ppe, name='acknowledge'),
]
