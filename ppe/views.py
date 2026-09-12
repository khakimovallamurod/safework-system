import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import PPEType, PPEIssue
from accounts.models import UserProfile, SystemNotification
from industries.models import Industry
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()

def get_user_organization_id(profile):
    if not profile:
        return None
    if profile.role == UserProfile.ROLE_ORG_LEADER:
        return profile.id
    return profile.organization_id

def get_allowed_employees_for_profile(profile, user):
    if user.is_superuser:
        return User.objects.all()
    if not profile:
        return User.objects.none()
    if profile.role == UserProfile.ROLE_ORG_LEADER:
        return User.objects.filter(Q(profile__organization_id=profile.id) | Q(profile__organization=profile) | Q(id=user.id))
    elif profile.role == UserProfile.ROLE_DEPARTMENT_ADMIN and profile.department_id:
        return User.objects.filter(profile__department_id=profile.department_id)
    elif profile.role == UserProfile.ROLE_SECTION_ADMIN and profile.section_id:
        return User.objects.filter(profile__section_id=profile.section_id)
    return User.objects.none()

def get_ppe_types_for_profile(profile):
    if not profile:
        return PPEType.objects.none()
    if profile.role == UserProfile.ROLE_SUPER_ADMIN:
        return PPEType.objects.all()
    org_id = get_user_organization_id(profile)
    if org_id:
        return PPEType.objects.filter(Q(organization_id=org_id) | Q(organization__isnull=True))
    return PPEType.objects.none()

@login_required
def ppe_dashboard(request):
    profile = getattr(request.user, 'profile', None)
    
    ppe_types = get_ppe_types_for_profile(profile)
    employees = UserProfile.objects.all().select_related('user', 'department', 'section', 'industry').order_by('section__name', 'user__first_name')
    industries = Industry.objects.all()
    
    selected_industry = request.GET.get('industry', '')
    selected_accept_status = request.GET.get('accept_status', '')
    
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
        elif profile.role == UserProfile.ROLE_WORKER:
            employees = employees.filter(user=request.user)
        else:
            employees = employees.none()
    else:
        employees = employees.none()

    # Filter parameter
    status_filter = request.GET.get('status', request.GET.get('accept_status', '')).strip().lower()

    # Calculate stats
    now = timezone.now().date()
    seven_days_from_now = now + timezone.timedelta(days=7)
    
    all_issues = PPEIssue.objects.filter(employee__in=[e.user for e in employees])
    total_issued_count = all_issues.count()
    expired_issues_count = all_issues.filter(expiration_date__lt=now).count()
    expiring_soon_count = all_issues.filter(expiration_date__gte=now, expiration_date__lte=seven_days_from_now).count()
    accepted_issues_count = all_issues.filter(status='accepted', expiration_date__gte=now).count()
    pending_issues_count = all_issues.filter(status='pending').count()
    
    total_required = employees.count() * ppe_types.count()
    total_provided = all_issues.filter(status='accepted', expiration_date__gte=now).count()
    
    provision_percentage = 0
    if total_required > 0:
        provision_percentage = int((total_provided / total_required) * 100)

    if selected_industry:
        employees = employees.filter(industry_id=selected_industry)

    # Pre-calculate issues to avoid N+1 query problem
    emp_issues_dict = {}
    for issue in all_issues:
        if issue.employee_id not in emp_issues_dict:
            emp_issues_dict[issue.employee_id] = []
        emp_issues_dict[issue.employee_id].append(issue)

    # Full matrix for template and stats
    full_matrix = []
    for emp in employees:
        row = {
            'employee': emp,
            'ppes': {},
            'has_pending': False,
            'has_accepted': False,
            'has_expired': False,
            'has_expiring': False,
            'has_missing': False,
            'has_issued': False,
            'total_issued_for_emp': 0,
        }
        emp_issues = emp_issues_dict.get(emp.user_id, [])
        for pt in ppe_types:
            pt_issues = [i for i in emp_issues if i.ppe_type_id == pt.id]
            pt_issues.sort(key=lambda x: x.issue_date, reverse=True)
            issue = pt_issues[0] if pt_issues else None
            
            if issue:
                row['has_issued'] = True
                row['total_issued_for_emp'] += 1
                if issue.status != 'accepted':
                    status_class = 'pending'
                    row['has_pending'] = True
                elif issue.expiration_date < now:
                    status_class = 'expired'
                    row['has_expired'] = True
                elif issue.expiration_date <= seven_days_from_now:
                    status_class = 'expiring'
                    row['has_expiring'] = True
                    row['has_accepted'] = True
                else:
                    status_class = 'active'
                    row['has_accepted'] = True
                    
                row['ppes'][pt.id] = {'issue': issue, 'status_class': status_class, 'accept_status': issue.status}
            else:
                row['ppes'][pt.id] = None
                row['has_missing'] = True
                
        full_matrix.append(row)

    # Calculate employee counts for cards
    emp_accepted_count = sum(1 for r in full_matrix if r['has_accepted'])
    emp_pending_count = sum(1 for r in full_matrix if r['has_pending'])
    emp_expired_count = sum(1 for r in full_matrix if r['has_expired'])
    emp_expiring_count = sum(1 for r in full_matrix if r['has_expiring'])
    emp_missing_count = sum(1 for r in full_matrix if r['has_missing'])
    emp_issued_count = sum(1 for r in full_matrix if r['has_issued'])

    # Apply filter
    filtered_matrix = full_matrix
    if status_filter == 'accepted':
        filtered_matrix = [r for r in full_matrix if r['has_accepted']]
    elif status_filter == 'pending':
        filtered_matrix = [r for r in full_matrix if r['has_pending']]
    elif status_filter == 'expired':
        filtered_matrix = [r for r in full_matrix if r['has_expired']]
    elif status_filter == 'expiring':
        filtered_matrix = [r for r in full_matrix if r['has_expiring']]
    elif status_filter == 'missing':
        filtered_matrix = [r for r in full_matrix if r['has_missing']]
    elif status_filter == 'issued':
        filtered_matrix = [r for r in full_matrix if r['has_issued']]

    # Group by department
    grouped_matrix = {}
    for row in filtered_matrix:
        dept = row['employee'].department
        dept_name = dept.name if dept else "Boshqa xodimlar (Bo'limsiz)"
        if dept_name not in grouped_matrix:
            grouped_matrix[dept_name] = []
        grouped_matrix[dept_name].append(row)
        
    # Sort dict by keys just in case
    grouped_matrix = dict(sorted(grouped_matrix.items()))

    can_manage = profile and profile.role in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]
    pending_issues = PPEIssue.objects.filter(employee=request.user, status='pending')

    context = {
        'ppe_types': ppe_types,
        'employees': employees,
        'industries': industries,
        'selected_industry': selected_industry,
        'selected_accept_status': selected_accept_status,
        'status_filter': status_filter,
        'grouped_matrix': grouped_matrix,
        'provision_percentage': provision_percentage,
        'total_issued_count': total_issued_count,
        'accepted_issues_count': accepted_issues_count,
        'pending_issues_count': pending_issues_count,
        'expired_issues_count': expired_issues_count,
        'expiring_soon_count': expiring_soon_count,
        'emp_accepted_count': emp_accepted_count,
        'emp_pending_count': emp_pending_count,
        'emp_expired_count': emp_expired_count,
        'emp_expiring_count': emp_expiring_count,
        'emp_missing_count': emp_missing_count,
        'emp_issued_count': emp_issued_count,
        'can_manage': can_manage,
        'pending_issues': pending_issues,
        'now': now,
        'seven_days_from_now': seven_days_from_now,
    }
    
    return render(request, 'ppe/dashboard.html', context)


@login_required
def create_ppe_type(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return JsonResponse({'success': False, 'error': "Ruxsat etilmagan"})

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            org_id = get_user_organization_id(profile)
            PPEType.objects.create(name=name, organization_id=org_id)
            return redirect('ppe:dashboard')
    
    return redirect('ppe:dashboard')


@login_required
def issue_ppe(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return JsonResponse({'success': False, 'error': "Ruxsat etilmagan"})

    if request.method == 'POST':
        employee_ids = request.POST.getlist('employees')
        ppe_type_ids = request.POST.getlist('ppe_types')
        issue_date = request.POST.get('issue_date')
        expiration_date = request.POST.get('expiration_date')
        condition = request.POST.get('condition')
        
        try:
            allowed_employees = get_allowed_employees_for_profile(profile, request.user)
            valid_employees = list(allowed_employees.filter(id__in=employee_ids))
            if not valid_employees:
                messages.error(request, "Tanlangan xodimlar sizning tashkilotingizga tegishli emas.")
                return redirect('ppe:dashboard')

            for ppe_type_id in ppe_type_ids:
                ppe_type = get_object_or_404(get_ppe_types_for_profile(profile), id=ppe_type_id)
                for user in valid_employees:
                    issue = PPEIssue.objects.create(
                        employee=user,
                        ppe_type=ppe_type,
                        issued_by=request.user,
                        issue_date=issue_date,
                        expiration_date=expiration_date,
                        condition=condition,
                        status='pending'
                    )
                    
                    # Send notification
                    SystemNotification.objects.create(
                        user=user,
                        title="Yangi IHV berildi",
                        message=f"Sizga yangi {ppe_type.name} berildi. Iltimos, tizimga kirib qabul qilganingizni tasdiqlang.",
                        type='system',
                        url=f"/ppe/"
                    )
            return redirect('ppe:dashboard')
        except Exception as e:
            pass
            
    return redirect('ppe:dashboard')


@login_required
def acknowledge_ppe(request, pk):
    if request.method == 'POST':
        issue = get_object_or_404(PPEIssue, pk=pk, employee=request.user)
        issue.status = 'accepted'
        issue.acknowledged_at = timezone.now()
        issue.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
def ppe_type_list(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER, UserProfile.ROLE_SUPER_ADMIN]:
        return redirect('ppe:dashboard')
        
    ppe_types = get_ppe_types_for_profile(profile)
    return render(request, 'ppe/type_list.html', {'ppe_types': ppe_types})

@login_required
def edit_ppe_type(request, pk):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER, UserProfile.ROLE_SUPER_ADMIN]:
        return redirect('ppe:type_list')
        
    ppe_type = get_object_or_404(get_ppe_types_for_profile(profile), pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            ppe_type.name = name
            ppe_type.save()
        return redirect('ppe:type_list')
    return redirect('ppe:type_list')

@login_required
def delete_ppe_type(request, pk):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER, UserProfile.ROLE_SUPER_ADMIN]:
        return redirect('ppe:type_list')
        
    ppe_type = get_object_or_404(get_ppe_types_for_profile(profile), pk=pk)
    if request.method == 'POST':
        ppe_type.delete()
    return redirect('ppe:type_list')

@login_required
def edit_ppe_issue(request, pk):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return JsonResponse({'success': False, 'error': "Ruxsat etilmagan"})

    issue = get_object_or_404(PPEIssue, pk=pk)
    if request.method == 'POST':
        issue.issue_date = request.POST.get('issue_date', issue.issue_date)
        issue.expiration_date = request.POST.get('expiration_date', issue.expiration_date)
        issue.condition = request.POST.get('condition', issue.condition)
        issue.save()
        return redirect('ppe:dashboard')
    
    return redirect('ppe:dashboard')

@login_required
def delete_ppe_issue(request, pk):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role not in [UserProfile.ROLE_DEPARTMENT_ADMIN, UserProfile.ROLE_SECTION_ADMIN, UserProfile.ROLE_ORG_LEADER]:
        return JsonResponse({'success': False, 'error': "Ruxsat etilmagan"})

    issue = get_object_or_404(PPEIssue, pk=pk)
    if request.method == 'POST':
        issue.delete()
        return redirect('ppe:dashboard')
        
    return redirect('ppe:dashboard')

