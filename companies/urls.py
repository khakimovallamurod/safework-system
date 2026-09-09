from django.urls import path

from companies.views import CompanyListView
from companies.views_tests import (
    TestListView, TestCreateView, TestEditView, TestDeleteView, TestStopView,
    TestDetailView, TestToggleStatusView, TestPracticePermissionsView,
    QuestionCreateView, QuestionDeleteView,
    QuizStartView, QuizTakeView, QuizResultView
)

app_name = 'companies'

urlpatterns = [
    path('', CompanyListView.as_view(), name='list'),
    
    # Test Management URLs
    path('tests/', TestListView.as_view(), name='test_list'),
    path('tests/create/', TestCreateView.as_view(), name='test_create'),
    path('tests/<int:pk>/edit/', TestEditView.as_view(), name='test_edit'),
    path('tests/<int:pk>/delete/', TestDeleteView.as_view(), name='test_delete'),
    path('tests/<int:pk>/stop/', TestStopView.as_view(), name='test_stop'),
    path('tests/<int:pk>/toggle-status/', TestToggleStatusView.as_view(), name='test_toggle_status'),
    path('tests/<int:pk>/practices/', TestPracticePermissionsView.as_view(), name='test_practice_permissions'),
    path('tests/<int:pk>/', TestDetailView.as_view(), name='test_detail'),
    
    # Question Management URLs
    path('tests/<int:test_pk>/questions/add/', QuestionCreateView.as_view(), name='question_create'),
    path('tests/<int:test_pk>/questions/<int:pk>/delete/', QuestionDeleteView.as_view(), name='question_delete'),
    
    # Quiz Taking URLs
    path('practice/<int:practice_pk>/tests/<int:test_pk>/start/', QuizStartView.as_view(), name='quiz_start'),
    path('quiz/attempt/<int:attempt_pk>/', QuizTakeView.as_view(), name='quiz_take'),
    path('quiz/attempt/<int:attempt_pk>/result/', QuizResultView.as_view(), name='quiz_result'),
]
