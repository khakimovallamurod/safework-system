from django.urls import path
from . import views

app_name = 'violations'

urlpatterns = [
    path('', views.violations_dashboard, name='dashboard'),
    path('create/', views.create_violation, name='create'),
    path('unblock/<int:employee_id>/', views.unblock_employee, name='unblock'),
    path('my/', views.my_violations, name='my_violations'),
    path('employee/<int:employee_id>/', views.employee_violations_detail, name='employee_detail'),
    path('types/', views.type_list, name='type_list'),
    path('types/create/', views.create_type, name='create_type'),
    path('types/edit/<int:pk>/', views.edit_type, name='edit_type'),
    path('types/delete/<int:pk>/', views.delete_type, name='delete_type'),
    path('letter/<int:pk>/file/', views.letter_file_view, name='letter_file'),
]
