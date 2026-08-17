from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View, TemplateView
from django.db.models import Count, Q

from accounts.models import UserProfile, SystemNotification
from companies.models import CertificateType, EmployeeCertificate

class OrganizationLeaderRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        profile = getattr(self.request.user, 'profile', None)
        return profile and profile.role == UserProfile.ROLE_ORG_LEADER


class CertificateTypeListView(LoginRequiredMixin, OrganizationLeaderRequiredMixin, ListView):
    model = CertificateType
    template_name = 'certificates/type_list.html'
    context_object_name = 'types'
    
    def get_queryset(self):
        return CertificateType.objects.all()

class CertificateTypeCreateView(LoginRequiredMixin, OrganizationLeaderRequiredMixin, CreateView):
    model = CertificateType
    fields = ['name']
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.save()
        messages.success(self.request, "Sertifikat turi muvaffaqiyatli qo'shildi.")
        return redirect('certificate-types')

class CertificateTypeEditView(LoginRequiredMixin, OrganizationLeaderRequiredMixin, UpdateView):
    model = CertificateType
    fields = ['name']
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Sertifikat turi muvaffaqiyatli yangilandi.")
        return redirect('certificate-types')

class CertificateTypeDeleteView(LoginRequiredMixin, OrganizationLeaderRequiredMixin, DeleteView):
    model = CertificateType
    success_url = reverse_lazy('certificate-types')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        messages.success(request, "Sertifikat turi o'chirildi.")
        return redirect(self.success_url)


class CertificateDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'certificates/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'profile', None)
        
        
        # Boshqalar yuborgan sertifikatlar turlari va soni
        types_with_counts = []
        all_types = CertificateType.objects.all()
        
        for ctype in all_types:
            count = 0
            if profile.role == UserProfile.ROLE_ORG_LEADER:
                # Tashkilot rahbari hamma sertifikatlarni ko'radi
                count = EmployeeCertificate.objects.filter(certificate_type=ctype).count()
            elif profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department:
                # Boshqarma nazoratchisi o'z boshqarmasiga tegishli xodimlarni
                count = EmployeeCertificate.objects.filter(
                    certificate_type=ctype,
                    user__profile__department=profile.department
                ).count()
            elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section:
                # Bo'lim nazoratchisi o'z bo'limiga tegishli
                count = EmployeeCertificate.objects.filter(
                    certificate_type=ctype,
                    user__profile__section=profile.section
                ).count()
                
            types_with_counts.append({
                'type': ctype,
                'count': count
            })
                
        context['types_with_counts'] = types_with_counts
        context['certificate_types'] = all_types # Qo'shish formasi uchun
        
        # Jamoa a'zolari (nazoratchilar ularga sertifikat yuklashi uchun)
        team_members = []
        if profile.role == UserProfile.ROLE_ORG_LEADER:
            team_members = UserProfile.objects.exclude(role=UserProfile.ROLE_SUPER_ADMIN).select_related('user')
        elif profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department:
            team_members = UserProfile.objects.filter(department=profile.department).select_related('user')
        elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section:
            team_members = UserProfile.objects.filter(section=profile.section).select_related('user')
        context['team_members'] = team_members
        
        return context


class EmployeeCertificateCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeCertificate
    fields = ['certificate_type', 'user', 'file']
    
    def post(self, request, *args, **kwargs):
        cert_type_id = request.POST.get('certificate_type')
        user_id = request.POST.get('user', request.user.id) # Agar tanlanmasa o'zi
        file = request.FILES.get('file')
        
        if cert_type_id and file:
            cert = EmployeeCertificate.objects.create(
                certificate_type_id=cert_type_id,
                user_id=user_id,
                file=file
            )
            
            # Xodimning o'ziga bildirishnoma (agar u o'zi yuklamagan bo'lsa)
            if str(user_id) != str(request.user.id):
                SystemNotification.objects.create(
                    user_id=user_id,
                    title="Yangi sertifikat biriktirildi",
                    message=f"Sizga '{cert.certificate_type.name}' nomli sertifikat biriktirildi.",
                    type='system',
                    url=reverse('my-certificates')
                )
                
            # Xodimning rahbarlariga (bo'lim va boshqarma nazoratchilari) bildirishnoma
            try:
                target_user_profile = UserProfile.objects.get(user_id=user_id)
                # O'ziga o'zi bildirishnoma yubormasligi uchun
                
                # Bo'lim nazoratchisiga
                if target_user_profile.section:
                    section_admins = UserProfile.objects.filter(section=target_user_profile.section, role=UserProfile.ROLE_SECTION_ADMIN)
                    for admin in section_admins:
                        if str(admin.user.id) != str(request.user.id):
                            SystemNotification.objects.create(
                                user_id=admin.user.id,
                                title="Xodimga sertifikat yuklandi",
                                message=f"Bo'limingizdagi xodim {target_user_profile.full_name} ga yangi sertifikat yuklandi.",
                                type='system',
                                url=reverse('certificate-dashboard')
                            )
                            
                # Boshqarma nazoratchisiga
                if target_user_profile.department:
                    dept_admins = UserProfile.objects.filter(department=target_user_profile.department, role=UserProfile.ROLE_DEPARTMENT_ADMIN)
                    for admin in dept_admins:
                        if str(admin.user.id) != str(request.user.id):
                            SystemNotification.objects.create(
                                user_id=admin.user.id,
                                title="Xodimga sertifikat yuklandi",
                                message=f"Boshqarmangizdagi xodim {target_user_profile.full_name} ga yangi sertifikat yuklandi.",
                                type='system',
                                url=reverse('certificate-dashboard')
                            )
            except UserProfile.DoesNotExist:
                pass
                
            messages.success(request, "Sertifikat muvaffaqiyatli yuklandi.")
        else:
            messages.error(request, "Iltimos, barcha maydonlarni to'ldiring.")
            
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('my-certificates')


class CertificateHierarchyView(LoginRequiredMixin, TemplateView):
    template_name = 'certificates/hierarchy.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        type_id = self.kwargs.get('type_id')
        ctype = get_object_or_404(CertificateType, id=type_id)
        profile = getattr(self.request.user, 'profile', None)
        
        context['certificate_type'] = ctype
        
        # Filtirlash
        qs = EmployeeCertificate.objects.filter(certificate_type=ctype).select_related(
            'user__profile', 'user__profile__department', 'user__profile__section'
        )
        
        if profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department:
            qs = qs.filter(user__profile__department=profile.department)
        elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section:
            qs = qs.filter(user__profile__section=profile.section)
        elif profile.role == UserProfile.ROLE_WORKER:
            qs = qs.none() # Oddiy xodim boshqalarnikini ko'rmaydi
            
        # Guruhlash o'rniga yassi ro'yxat uzatiladi
        context['certificates'] = qs
        
        # Boshqarmalar va bo'limlar ro'yxatini filterlash uchun jo'natamiz
        structures = set()
        for cert in qs:
            if profile.role in [UserProfile.ROLE_ORG_LEADER, UserProfile.ROLE_DEPARTMENT_ADMIN]:
                if cert.user.profile.department:
                    structures.add(cert.user.profile.department.name)
                else:
                    structures.add("Tashkilot rahbariyati")
                    
            if profile.role in [UserProfile.ROLE_ORG_LEADER, UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN]:
                if cert.user.profile.section:
                    structures.add(cert.user.profile.section.name)
                else:
                    structures.add("Asosiy xodimlar")
                
        context['departments'] = sorted(list(structures))
        
        return context

class MyCertificatesView(LoginRequiredMixin, TemplateView):
    template_name = 'certificates/my_certificates.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # O'zining sertifikatlari turi va ularning ro'yxati
        my_certificates = EmployeeCertificate.objects.filter(user=self.request.user).select_related('certificate_type')
        my_certs_by_type = {}
        for cert in my_certificates:
            my_certs_by_type.setdefault(cert.certificate_type, []).append(cert)
            
        context['my_certs_by_type'] = my_certs_by_type
        context['certificate_types'] = CertificateType.objects.all()
        
        # Jamoa a'zolari (nazoratchilar ularga sertifikat yuklashi uchun)
        profile = getattr(self.request.user, 'profile', None)
        team_members = []
        if profile and profile.role == UserProfile.ROLE_ORG_LEADER:
            team_members = UserProfile.objects.exclude(role=UserProfile.ROLE_SUPER_ADMIN).select_related('user')
        elif profile and profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department:
            team_members = UserProfile.objects.filter(department=profile.department).select_related('user')
        elif profile and profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section:
            team_members = UserProfile.objects.filter(section=profile.section).select_related('user')
        context['team_members'] = team_members
        
        return context

class CertificatePdfView(LoginRequiredMixin, TemplateView):
    template_name = 'certificates/pdf_view.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cert_id = self.kwargs.get('pk')
        cert = get_object_or_404(EmployeeCertificate, id=cert_id)
        
        # O'quvchi bu sertifikatni ko'rishga ruxsati borligini tekshirish kiritish mumkin
        # (hozircha oddiy)
        
        context['certificate'] = cert
        return context
