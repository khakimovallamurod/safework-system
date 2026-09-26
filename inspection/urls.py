from django.urls import path
from inspection.views import (
    InspectionDashboardView,
    InspectionCompanyRegistryView,
    InspectionCompanyDetailView,
    InspectionWorkerDetailView,
    InspectionEntryGuidelinesView,
    InspectionMandatoryGuidelinesView,
    InspectionInternalGuidelinesView,
    InspectionProfessionGuidelinesView,
    InspectionPracticesView,
    InspectionTestResultsView,
    InspectionViolationsView,
    InspectionPPEView,
    InspectionCertificatesView,
    InspectionMedicalView,
    InspectionAdminManageView,
    InspectionToggleStatusView,
)

app_name = 'inspection'

urlpatterns = [
    # Inspeksiya boshqaruv paneli va korxonalar (faqat o'qish)
    path('', InspectionDashboardView.as_view(), name='dashboard'),
    path('korxonalar/', InspectionCompanyRegistryView.as_view(), name='companies'),
    path('korxona/<int:pk>/', InspectionCompanyDetailView.as_view(), name='company-detail'),
    path('xodim/<int:pk>/', InspectionWorkerDetailView.as_view(), name='worker-detail'),

    # Yo'riqnomalar nazorati
    path('yoriqnomalar/kirish/', InspectionEntryGuidelinesView.as_view(), name='guidelines-entry'),
    path('yoriqnomalar/majburiy/', InspectionMandatoryGuidelinesView.as_view(), name='guidelines-mandatory'),
    path('yoriqnomalar/ichki/', InspectionInternalGuidelinesView.as_view(), name='guidelines-internal'),
    path('yoriqnomalar/kasbiy/', InspectionProfessionGuidelinesView.as_view(), name='guidelines-profession'),

    # Stajirovka va bilimni baholash
    path('stajirovka/', InspectionPracticesView.as_view(), name='practices'),
    path('test-natijalari/', InspectionTestResultsView.as_view(), name='tests'),

    # Qoidabuzarliklar, IHV, sertifikatlar, tibbiy ko'rik
    path('qoidabuzarliklar/', InspectionViolationsView.as_view(), name='violations'),
    path('ihv/', InspectionPPEView.as_view(), name='ppe'),
    path('sertifikatlar/', InspectionCertificatesView.as_view(), name='certificates'),
    path('tibbiy-korik/', InspectionMedicalView.as_view(), name='medical'),

    # Super admin uchun inspektorlarni boshqarish
    path('boshqaruv/', InspectionAdminManageView.as_view(), name='admin-manage'),
    path('toggle-status/<int:pk>/', InspectionToggleStatusView.as_view(), name='toggle-status'),
]
