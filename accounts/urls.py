from django.urls import path

from accounts.views import (
    AdminLoginView,
    AdminLogoutView,
    DashboardView,
    LandingPageView,
    OrganizationLeaderRegisterView,
    RegisterChoiceView,
    ToggleUserBlockView,
    UserManagementView,
    WorkerRegisterView,
)

urlpatterns = [
    path('', LandingPageView.as_view(), name='home'),
    path('login/', AdminLoginView.as_view(), name='login'),
    path('logout/', AdminLogoutView.as_view(), name='logout'),
    path('register/', RegisterChoiceView.as_view(), name='register-choice'),
    path('register/leader/', OrganizationLeaderRegisterView.as_view(), name='register-leader'),
    path('register/worker/', WorkerRegisterView.as_view(), name='register-worker'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('users/', UserManagementView.as_view(), name='users'),
    path('users/<int:pk>/toggle-block/', ToggleUserBlockView.as_view(), name='toggle-block'),
]
