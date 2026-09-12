from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from .models import Violation, ViolationType, ExplanationLetter
from accounts.models import UserProfile, SystemNotification
from accounts.notifications import send_action_notification
from industries.models import Industry
import datetime

User = get_user_model()

def check_and_block_employee(employee):
    """
    Check if employee has 2 or more active violations in the last 30 days.
    If so, block them and notify Director, OTX, and Section Admin.
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
            emp_name = profile.full_name or employee.username
            sec_name = profile.section.name if profile.section else (profile.department.name if profile.department else "")
            sec_info = f" ({sec_name})" if sec_name else ""
            detail_url = f"/violations/employee/{employee.id}/"

            send_action_notification(
                title="Diqqat: Xodim ishdan chetlashtirildi",
                message=f"Xodim {emp_name}{sec_info} 2 marotaba ogohlantirish olgani sababli tizimda ishdan vaqtincha chetlashtirildi (bloklandi).",
                notif_type='violation',
                url=detail_url,
                section=profile.section,
                department=profile.department,
                target_users=[employee]
            )
        elif active_violations_count < 2 and profile.is_blocked_by_violations:
            profile.is_blocked_by_violations = False
            profile.save()


def get_allowed_employees_for_user(user):
    """
    Foydalanuvchi o'ziga qarashli tashkilot, boshqarma yoki bo'lim xodimlarinigina boshqara oladi.
    Begona tashkilot xodimlari ustidan amallar bajarish taqiqlanadi (IDOR himoyasi).
    """
    if user.is_superuser:
        return User.objects.all()

    profile = getattr(user, 'profile', None)
    if not profile:
        return User.objects.none()

    if profile.role == UserProfile.ROLE_ORG_LEADER:
        return User.objects.filter(
            Q(profile__organization_id=profile.id) | Q(profile__organization=profile) | Q(id=user.id)
        )
    elif profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department_id:
        return User.objects.filter(profile__department_id=profile.department_id)
    elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section_id:
        return User.objects.filter(profile__section_id=profile.section_id)

    return User.objects.none()


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
    if request.user.is_superuser:
        pass
    elif profile:
        if profile.role == UserProfile.ROLE_ORG_LEADER:
            employees = employees.filter(Q(organization_id=profile.id) | Q(id=profile.id))
        elif profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department_id:
            employees = employees.filter(department_id=profile.department_id)
        elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section_id:
            employees = employees.filter(section_id=profile.section_id)
        else:
            employees = employees.none()
    else:
        employees = employees.none()

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

    # Summary statistics across all employees
    total_violators = sum(1 for r in matrix if r['total_violations'] > 0)
    total_active_violators = sum(1 for r in matrix if r['active_violations_last_30_days'] > 0)
    total_blocked = sum(1 for r in matrix if r['is_blocked'])
    total_clean = sum(1 for r in matrix if r['total_violations'] == 0)
    total_violations_count = all_violations.count()

    # Filter parameter
    filter_type = request.GET.get('filter', 'all').strip().lower()
    filtered_matrix = matrix
    if filter_type == 'active':
        filtered_matrix = [r for r in matrix if r['active_violations_last_30_days'] > 0]
    elif filter_type == 'blocked':
        filtered_matrix = [r for r in matrix if r['is_blocked']]
    elif filter_type in ['violators', 'has_violations']:
        filtered_matrix = [r for r in matrix if r['total_violations'] > 0]
    elif filter_type == 'clean':
        filtered_matrix = [r for r in matrix if r['total_violations'] == 0]

    # Group by department
    grouped_matrix = {}
    for row in filtered_matrix:
        dept = row['employee'].department
        dept_name = dept.name if dept else "Boshqa xodimlar (Bo'limsiz)"
        if dept_name not in grouped_matrix:
            grouped_matrix[dept_name] = []
        grouped_matrix[dept_name].append(row)
        
    grouped_matrix = dict(sorted(grouped_matrix.items()))
    
    violation_types = ViolationType.objects.all()

    context = {
        'grouped_matrix': grouped_matrix,
        'total_employees_count': len(matrix),
        'total_violators': total_violators,
        'total_active_violators': total_active_violators,
        'total_blocked': total_blocked,
        'total_clean': total_clean,
        'total_violations_count': total_violations_count,
        'filter_type': filter_type,
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
        employee_ids = request.POST.getlist('employee_ids')
        if not employee_ids:
            emp_id = request.POST.get('employee_id')
            if emp_id:
                employee_ids = [emp_id]

        v_type = request.POST.get('violation_type')
        reason = request.POST.get('reason')
        date_str = request.POST.get('date')
        image = request.FILES.get('image')

        if not employee_ids:
            messages.error(request, "Hech bo‘lmaganda bitta xodimni tanlang.")
            return redirect('violations:dashboard')

        try:
            if image:
                from core.validators import validate_file_security, validate_image_extension
                validate_file_security(image)
                validate_image_extension(image)

            v_type_obj = ViolationType.objects.get(id=v_type)
            allowed_users = get_allowed_employees_for_user(request.user)
            employees = list(allowed_users.filter(id__in=employee_ids).select_related('profile', 'profile__section', 'profile__department'))
            if not employees:
                messages.error(request, "Tanlangan xodim(lar) sizning tashkilotingizga tegishli emas yoki topilmadi.")
                return redirect('violations:dashboard')

            issuer_profile = getattr(request.user, 'profile', None)
            issuer_name = (issuer_profile.full_name if issuer_profile and issuer_profile.full_name else request.user.username)
            if issuer_profile and issuer_profile.position:
                issuer_title = issuer_profile.position
            elif issuer_profile and issuer_profile.section:
                issuer_title = f"{issuer_profile.section.name} mas'uli"
            elif issuer_profile and issuer_profile.department:
                issuer_title = f"{issuer_profile.department.name} nazoratchisi"
            else:
                issuer_title = "Mas'ul xodim"

            date_val = date_str if date_str else timezone.now().date()
            saved_image = None
            created_count = 0

            for idx, employee in enumerate(employees):
                v_image = image if idx == 0 else (saved_image if saved_image else None)
                v = Violation.objects.create(
                    employee=employee,
                    issued_by=request.user,
                    violation_type=v_type_obj,
                    reason=reason,
                    date=date_val,
                    image=v_image
                )
                if idx == 0 and v.image:
                    saved_image = v.image

                created_count += 1

                # Nechanchi faol ogohlantirish ekanligini aniqlash
                thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
                recent_count = Violation.objects.filter(
                    employee=employee,
                    date__gte=thirty_days_ago,
                    is_active=True
                ).count()

                emp_profile = getattr(employee, 'profile', None)
                emp_name = (emp_profile.full_name if emp_profile and emp_profile.full_name else employee.username)
                emp_section = getattr(emp_profile, 'section', None)
                emp_dept = getattr(emp_profile, 'department', None)

                detail_url = f"/violations/employee/{employee.id}/"
                notif_title = f"Qoidabuzarlik: {recent_count}-ogohlantirish"
                notif_msg = f"{issuer_title} ({issuer_name}) ishchi {emp_name}ga qoidabuzarlik bo‘yicha {recent_count}-ogohlantirish yubordi: «{v_type_obj.name}»."

                send_action_notification(
                    title=notif_title,
                    message=notif_msg,
                    notif_type='violation',
                    url=detail_url,
                    section=emp_section,
                    department=emp_dept,
                    target_users=[employee]
                )
                check_and_block_employee(employee)

            if created_count == 1:
                messages.success(request, f"{employees[0].profile.full_name or employees[0].username} uchun qoidabuzarlik muvaffaqiyatli saqlandi.")
            else:
                messages.success(request, f"{created_count} nafar xodim uchun qoidabuzarlik muvaffaqiyatli saqlandi.")

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
        
        allowed_users = get_allowed_employees_for_user(request.user)
        employee = get_object_or_404(allowed_users, id=employee_id)
        
        try:
            if file:
                from core.validators import validate_file_security, validate_document_extension
                validate_file_security(file)
                validate_document_extension(file)

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

            unblocker_profile = getattr(request.user, 'profile', None)
            unblocker_name = (unblocker_profile.full_name if unblocker_profile and unblocker_profile.full_name else request.user.username)
            emp_profile = getattr(employee, 'profile', None)
            emp_name = (emp_profile.full_name if emp_profile and emp_profile.full_name else employee.username)
            detail_url = f"/violations/employee/{employee.id}/"

            send_action_notification(
                title="Mehnatga ruxsat berildi",
                message=f"Mehnat muhofazasi va texnika xavfsizligi muhandisi ({unblocker_name}) xodim {emp_name}dan tushuntirish xatini olib, tizimda ishga ruxsat berdi.",
                notif_type='permission',
                url=detail_url,
                section=getattr(emp_profile, 'section', None),
                department=getattr(emp_profile, 'department', None),
                target_users=[employee]
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

    allowed_users = get_allowed_employees_for_user(request.user)
    employee = get_object_or_404(allowed_users, id=employee_id)
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
