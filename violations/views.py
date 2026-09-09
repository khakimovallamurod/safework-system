from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from .models import Violation, ViolationType, ExplanationLetter
from accounts.models import UserProfile, SystemNotification
from industries.models import Industry
import datetime

User = get_user_model()

def check_and_block_employee(employee):
    """
    Check if employee has 2 or more active violations in the last 30 days.
    If so, block them.
    """
    thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
    active_violations_count = Violation.objects.filter(
        employee=employee,
        date__gte=thirty_days_ago,
        is_active=True
    ).count()

    profile = getattr(employee, 'profile', None)
    if profile:
        if active_violations_count >= 2 and not profile.is_blocked_by_violations:
            profile.is_blocked_by_violations = True
            profile.save()
            SystemNotification.objects.create(
                user=employee,
                title="Tizimdan bloklandingiz",
                message="Sizda so'nggi oyda 2 yoki undan ortiq qoidabuzarlik qayd etilganligi sababli tizimdan vaqtincha bloklandingiz.",
                type='system'
            )
        elif active_violations_count < 2 and profile.is_blocked_by_violations:
            profile.is_blocked_by_violations = False
            profile.save()


@login_required
def violations_dashboard(request):
    profile = getattr(request.user, 'profile', None)
    
    # Identify if user is worker or admin
    is_worker = profile and profile.role == UserProfile.ROLE_WORKER
    if is_worker:
        return redirect('violations:my_violations')

    employees = UserProfile.objects.all().select_related('user', 'department', 'section', 'industry').order_by('department__name', 'user__first_name')
    industries = Industry.objects.all()
    
    selected_industry = request.GET.get('industry', '')
    
    # Filter based on roles
    if profile:
        if profile.role == UserProfile.ROLE_ORG_LEADER and profile.organization_id:
            employees = employees.filter(organization_id=profile.organization_id)
        elif profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department_id:
            employees = employees.filter(department_id=profile.department_id)
        elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section_id:
            employees = employees.filter(section_id=profile.section_id)

    if selected_industry:
        employees = employees.filter(industry_id=selected_industry)

    thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
    
    # Calculate violations per user
    all_violations = Violation.objects.filter(employee__in=[e.user for e in employees])
    
    emp_violations_dict = {}
    for v in all_violations:
        if v.employee_id not in emp_violations_dict:
            emp_violations_dict[v.employee_id] = []
        emp_violations_dict[v.employee_id].append(v)
        
    matrix = []
    for emp in employees:
        v_list = emp_violations_dict.get(emp.user_id, [])
        active_v_list = [v for v in v_list if v.is_active and v.date >= thirty_days_ago]
        
        row = {
            'employee': emp,
            'total_violations': len(v_list),
            'active_violations_last_30_days': len(active_v_list),
            'is_blocked': emp.is_blocked_by_violations,
            'violations': sorted(v_list, key=lambda x: x.date, reverse=True)[:5] # Show last 5
        }
        matrix.append(row)

    # Group by department
    grouped_matrix = {}
    for row in matrix:
        dept = row['employee'].department
        dept_name = dept.name if dept else "Boshqa xodimlar (Bo'limsiz)"
        if dept_name not in grouped_matrix:
            grouped_matrix[dept_name] = []
        grouped_matrix[dept_name].append(row)
        
    grouped_matrix = dict(sorted(grouped_matrix.items()))
    
    violation_types = ViolationType.objects.all()

    context = {
        'grouped_matrix': grouped_matrix,
        'violation_types': violation_types,
        'industries': industries,
        'selected_industry': selected_industry,
        'employees_queryset': employees,
    }
    return render(request, 'violations/dashboard.html', context)


@login_required
def create_violation(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role in [UserProfile.ROLE_WORKER]:
        messages.error(request, "Sizda qoidabuzarlik yaratish huquqi yo'q.")
        return redirect('violations:dashboard')

    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        v_type = request.POST.get('violation_type')
        reason = request.POST.get('reason')
        date_str = request.POST.get('date')
        image = request.FILES.get('image')
        
        try:
            employee = User.objects.get(id=employee_id)
            v_type_obj = ViolationType.objects.get(id=v_type)
            v = Violation.objects.create(
                employee=employee,
                issued_by=request.user,
                violation_type=v_type_obj,
                reason=reason,
                date=date_str if date_str else timezone.now().date(),
                image=image
            )
            SystemNotification.objects.create(
                user=employee,
                title="Yangi qoidabuzarlik",
                message=f"Sizga yangi qoidabuzarlik yozildi: {v_type_obj.name}",
                type='system',
                url='/violations/'
            )
            messages.success(request, "Qoidabuzarlik muvaffaqiyatli saqlandi.")
            check_and_block_employee(employee)
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
            
    return redirect('violations:dashboard')


@login_required
def unblock_employee(request, employee_id):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role in [UserProfile.ROLE_WORKER]:
        messages.error(request, "Sizda blokdan chiqarish huquqi yo'q.")
        return redirect('violations:dashboard')

    if request.method == 'POST':
        explanation_text = request.POST.get('explanation_text')
        file = request.FILES.get('file')
        
        employee = get_object_or_404(User, id=employee_id)
        
        try:
            ExplanationLetter.objects.create(
                employee=employee,
                unblocked_by=request.user,
                explanation_text=explanation_text,
                file=file
            )
            
            # Deactivate recent active violations to unblock them
            thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
            active_vs = Violation.objects.filter(employee=employee, is_active=True, date__gte=thirty_days_ago)
            for v in active_vs:
                v.is_active = False
                v.save()
                
            check_and_block_employee(employee)
            
            SystemNotification.objects.create(
                user=employee,
                title="Tizimdan blokdan chiqarildingiz",
                message="Sizning tushuntirish xatingiz qabul qilindi va tizimga kirishga ruxsat berildi.",
                type='system'
            )
            messages.success(request, "Xodim muvaffaqiyatli blokdan chiqarildi va tushuntirish xati saqlandi.")
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
            
    return redirect('violations:dashboard')


@login_required
def my_violations(request):
    violations = Violation.objects.filter(employee=request.user).select_related('violation_type', 'issued_by').order_by('-date', '-created_at')
    letters = ExplanationLetter.objects.filter(employee=request.user).select_related('unblocked_by').order_by('-created_at')
    
    context = {
        'violations': violations,
        'letters': letters
    }
    return render(request, 'violations/worker_view.html', context)


@login_required
def employee_violations_detail(request, employee_id):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role in [UserProfile.ROLE_WORKER]:
        messages.error(request, "Sizda bu sahifani ko'rish huquqi yo'q.")
        return redirect('violations:dashboard')

    employee = get_object_or_404(User, id=employee_id)
    violations = Violation.objects.filter(employee=employee).select_related('violation_type', 'issued_by').order_by('-date', '-created_at')
    letters = ExplanationLetter.objects.filter(employee=employee).select_related('unblocked_by').order_by('-created_at')
    
    context = {
        'target_employee': employee,
        'violations': violations,
        'letters': letters
    }
    return render(request, 'violations/employee_detail.html', context)


@login_required
def type_list(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return redirect('violations:dashboard')
        
    types = ViolationType.objects.all()
    return render(request, 'violations/type_list.html', {'types': types})

@login_required
def create_type(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return JsonResponse({'success': False, 'error': "Ruxsat etilmagan"})

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            ViolationType.objects.create(name=name)
            return redirect('violations:type_list')
    return redirect('violations:type_list')

@login_required
def edit_type(request, pk):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return redirect('violations:type_list')
        
    v_type = get_object_or_404(ViolationType, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            v_type.name = name
            v_type.save()
        return redirect('violations:type_list')
    return redirect('violations:type_list')

@login_required
def delete_type(request, pk):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return redirect('violations:type_list')
        
    v_type = get_object_or_404(ViolationType, pk=pk)
    if request.method == 'POST':
        v_type.delete()
    return redirect('violations:type_list')

@login_required
def letter_file_view(request, pk):
    letter = get_object_or_404(ExplanationLetter, pk=pk)
    
    profile = getattr(request.user, 'profile', None)
    can_manage = profile and profile.role in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]
    
    if request.user != letter.employee and not can_manage and not request.user.is_superuser:
        messages.error(request, "Sizda bu hujjatni ko'rish huquqi yo'q.")
        return redirect('violations:dashboard')
        
    back_url = request.META.get('HTTP_REFERER', reverse('violations:dashboard'))
    
    context = {
        'letter': letter,
        'pdf_url': letter.file.url if letter.file else '',
        'pdf_title': "Tushuntirish xati",
        'back_url': back_url,
    }
    return render(request, 'violations/letter_file_view.html', context)
